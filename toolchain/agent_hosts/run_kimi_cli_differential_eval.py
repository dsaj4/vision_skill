from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from statistics import mean
from typing import Any, Sequence

from toolchain.agent_hosts.kimi_code_host import KimiCodeHost
from toolchain.eval_factory.sync import resolve_package_evals
from toolchain.graders.capability_grader import grade_response_text
from toolchain.kimi_command import resolve_kimi_command


DEFAULT_JUDGE_MAX_CHARS = 4000
DEFAULT_TIMEOUT_SECONDS = 300


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_eval_ids(value: str | None) -> list[int] | None:
    if not value:
        return None
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "eval"


def _trim_for_judge(text: str, max_chars: int) -> str:
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized
    head = normalized[: max_chars // 2].strip()
    tail = normalized[-max_chars // 3 :].strip()
    return f"{head}\n\n...[truncated]...\n\n{tail}"


def _default_kimi_runner(args: list[str], cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    env = dict(os.environ)
    env.setdefault("PATH", "")
    user_bin = str(Path.home() / ".local" / "bin")
    if user_bin not in env["PATH"].split(";"):
        env["PATH"] = user_bin + ";" + env["PATH"]
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
        env=env,
    )
    return {
        "returncode": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _extract_resume_session_id(text: str) -> str | None:
    match = re.search(r"kimi\s+-r\s+([A-Za-z0-9_.:-]+)", text)
    return match.group(1) if match else None


def _extract_plain_assistant_text(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1]


def _run_plain_kimi_turns(
    turns: list[str],
    *,
    session_dir: Path,
    timeout_seconds: int,
    model: str | None = None,
) -> dict[str, Any]:
    session_dir.mkdir(parents=True, exist_ok=True)
    kimi_session_id: str | None = None
    transcript_turns: list[dict[str, Any]] = []
    stderr_log: list[str] = []

    for turn_index, text in enumerate(turns, start=1):
        args = [
            resolve_kimi_command(),
            "--print",
            "--final-message-only",
            "--work-dir",
            str(session_dir),
        ]
        if kimi_session_id:
            args.extend(["--session", kimi_session_id])
        if model or os.getenv("KIMI_CLI_MODEL"):
            args.extend(["--model", model or os.getenv("KIMI_CLI_MODEL", "")])
        args.extend(["--prompt", text])

        result = _default_kimi_runner(args, session_dir, timeout_seconds)
        if int(result["returncode"]) != 0:
            raise RuntimeError(
                "Plain Kimi CLI execution failed: "
                + str(result.get("stderr", "") or result.get("stdout", "")).strip()
            )

        stderr_text = str(result.get("stderr", "")).strip()
        if stderr_text:
            stderr_log.append(stderr_text)
        extracted_session_id = _extract_resume_session_id(stderr_text)
        if extracted_session_id:
            kimi_session_id = extracted_session_id

        assistant_text = _extract_plain_assistant_text(str(result.get("stdout", "")))
        transcript_turns.append(
            {
                "turn_index": turn_index,
                "user_text": text,
                "assistant_text": assistant_text,
                "events": [],
                "command_events": [],
                "warnings": [],
                "stderr": str(result.get("stderr", "")),
            }
        )

    return {
        "thread_id": kimi_session_id,
        "host_backend": "kimi-cli-plain",
        "turns": transcript_turns,
        "stderr": stderr_log,
    }


def _judge_prompt(user_prompt: str, response_a: str, response_b: str) -> str:
    return "\n".join(
        [
            "You are comparing two assistant answers for the same user request.",
            "Choose which answer better satisfies the user's request overall.",
            "Prioritize usefulness, correctness, naturalness, completeness, and protocol fit when the prompt explicitly requests a mode.",
            "Do not use markdown fences or any extra commentary.",
            'Return JSON only: {"winner":"A"|"B"|"tie","margin":0.0-1.0,"reason":"short reason"}',
            "",
            "User prompt:",
            user_prompt,
            "",
            "Response A:",
            response_a,
            "",
            "Response B:",
            response_b,
        ]
    )


def _parse_judge_decision(text: str) -> dict[str, Any]:
    payload = text.strip()
    if not payload:
        raise ValueError("Empty judge response.")

    start = payload.find("{")
    end = payload.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"Judge response is not JSON: {text}")

    parsed = json.loads(payload[start : end + 1])
    winner = str(parsed.get("winner", "tie")).strip().lower()
    if winner not in {"a", "b", "tie"}:
        winner = "tie"
    try:
        margin = float(parsed.get("margin", 0.0) or 0.0)
    except (TypeError, ValueError):
        margin = 0.0
    margin = max(0.0, min(1.0, margin))
    return {
        "winner": winner,
        "margin": margin,
        "reason": str(parsed.get("reason", "")).strip(),
    }


def _run_and_parse_judge_turn(
    *,
    prompt: str,
    judge_dir: Path,
    label: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    last_error: str | None = None

    for attempt in range(1, 4):
        attempt_prompt = prompt
        if attempt > 1:
            attempt_prompt = "\n".join(
                [
                    prompt,
                    "",
                    "IMPORTANT: Your previous reply was invalid.",
                    'Reply with exactly one compact JSON object like {"winner":"A","margin":0.3,"reason":"short reason"}.',
                    "No markdown. No backticks. No extra text.",
                ]
            )

        result = _run_plain_kimi_turns(
            [attempt_prompt],
            session_dir=judge_dir / label / f"attempt-{attempt}",
            timeout_seconds=timeout_seconds,
        )
        _write_json(judge_dir / label / f"attempt-{attempt}.json", result)

        assistant_text = str(result["turns"][-1].get("assistant_text", ""))
        try:
            decision = _parse_judge_decision(assistant_text)
            return {
                "decision": decision,
                "attempt": attempt,
                "fallback_used": attempt > 1,
                "raw_response": assistant_text,
            }
        except ValueError as exc:
            last_error = str(exc)

    return {
        "decision": {
            "winner": "tie",
            "margin": 0.0,
            "reason": "Judge returned invalid JSON after retries.",
        },
        "attempt": 3,
        "fallback_used": True,
        "raw_response": "",
        "error": last_error or "Judge returned invalid JSON after retries.",
    }


def _judge_pairwise_with_kimi(
    *,
    user_prompt: str,
    with_skill_text: str,
    without_skill_text: str,
    judge_dir: Path,
    timeout_seconds: int,
    judge_max_chars: int,
) -> dict[str, Any]:
    judge_dir.mkdir(parents=True, exist_ok=True)
    forward_prompt = _judge_prompt(
        user_prompt,
        _trim_for_judge(with_skill_text, judge_max_chars),
        _trim_for_judge(without_skill_text, judge_max_chars),
    )
    reversed_prompt = _judge_prompt(
        user_prompt,
        _trim_for_judge(without_skill_text, judge_max_chars),
        _trim_for_judge(with_skill_text, judge_max_chars),
    )

    forward = _run_and_parse_judge_turn(
        prompt=forward_prompt,
        judge_dir=judge_dir,
        label="forward",
        timeout_seconds=timeout_seconds,
    )
    reversed_result = _run_and_parse_judge_turn(
        prompt=reversed_prompt,
        judge_dir=judge_dir,
        label="reversed",
        timeout_seconds=timeout_seconds,
    )
    forward_decision = dict(forward["decision"])
    reversed_decision = dict(reversed_result["decision"])

    mapped_forward = {
        "a": "with_skill",
        "b": "without_skill",
        "tie": "tie",
    }[forward_decision["winner"]]
    mapped_reversed = {
        "a": "without_skill",
        "b": "with_skill",
        "tie": "tie",
    }[reversed_decision["winner"]]

    if mapped_forward == mapped_reversed:
        final_winner = mapped_forward
        tiebreak_used = False
        tiebreak_decision: dict[str, Any] | None = None
        tiebreak_meta: dict[str, Any] | None = None
    else:
        tiebreak_prompt = _judge_prompt(
            user_prompt,
            _trim_for_judge(with_skill_text, judge_max_chars),
            _trim_for_judge(without_skill_text, judge_max_chars),
        )
        tiebreak_meta = _run_and_parse_judge_turn(
            prompt=tiebreak_prompt,
            judge_dir=judge_dir,
            label="tiebreak",
            timeout_seconds=timeout_seconds,
        )
        tiebreak_decision = dict(tiebreak_meta["decision"])
        final_winner = {
            "a": "with_skill",
            "b": "without_skill",
            "tie": "tie",
        }[tiebreak_decision["winner"]]
        tiebreak_used = True

    margins = [forward_decision["margin"], reversed_decision["margin"]]
    if tiebreak_decision is not None:
        margins.append(tiebreak_decision["margin"])

    return {
        "forward_decision": forward_decision,
        "reversed_decision": reversed_decision,
        "tiebreak_decision": tiebreak_decision,
        "forward_winner": mapped_forward,
        "reversed_winner": mapped_reversed,
        "final_winner": final_winner,
        "tiebreak_used": tiebreak_used,
        "avg_margin": round(mean(margins), 4) if margins else 0.0,
        "judge_meta": {
            "forward_attempt": int(forward["attempt"]),
            "forward_fallback_used": bool(forward["fallback_used"]),
            "reversed_attempt": int(reversed_result["attempt"]),
            "reversed_fallback_used": bool(reversed_result["fallback_used"]),
            "tiebreak_attempt": int(tiebreak_meta["attempt"]) if tiebreak_meta else None,
            "tiebreak_fallback_used": bool(tiebreak_meta["fallback_used"]) if tiebreak_meta else None,
            "forward_error": forward.get("error"),
            "reversed_error": reversed_result.get("error"),
            "tiebreak_error": tiebreak_meta.get("error") if tiebreak_meta else None,
        },
    }


def _eval_dir_name(eval_item: dict[str, Any]) -> str:
    eval_id = int(eval_item["id"])
    certified = eval_item.get("certified_metadata", {})
    scenario_id = certified.get("scenario_id", "")
    variant_type = certified.get("variant_type", "")
    candidate = "-".join(part for part in [str(scenario_id), str(variant_type)] if part)
    return f"eval-{eval_id}-{_slugify(candidate)}" if candidate else f"eval-{eval_id}"


def _build_eval_metadata(eval_item: dict[str, Any], eval_name: str) -> dict[str, Any]:
    return {
        "eval_id": int(eval_item["id"]),
        "eval_name": eval_name,
        "prompt": eval_item.get("prompt", ""),
        "assertions": list(eval_item.get("expectations", [])),
    }


def _turns_for_eval(eval_item: dict[str, Any]) -> list[str]:
    host_eval = eval_item.get("host_eval", {})
    script = host_eval.get("turn_script", [])
    if script:
        turns: list[str] = []
        for item in script:
            if isinstance(item, dict):
                turns.append(str(item.get("text", "")).strip())
            else:
                turns.append(str(item).strip())
        return [turn for turn in turns if turn]
    return [str(eval_item.get("prompt", "")).strip()]


def _filter_evals(
    evals: list[dict[str, Any]],
    *,
    eval_ids: list[int] | None,
    max_evals: int | None,
) -> list[dict[str, Any]]:
    filtered = list(evals)
    if eval_ids:
        selected = {int(item) for item in eval_ids}
        filtered = [item for item in filtered if int(item["id"]) in selected]
    if max_evals is not None:
        filtered = filtered[: max(0, int(max_evals))]
    return filtered


def run_kimi_cli_differential_eval(
    package_dir: str | Path,
    workspace_dir: str | Path,
    *,
    iteration_name: str,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    judge_max_chars: int = DEFAULT_JUDGE_MAX_CHARS,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    iteration_dir = workspace_path / iteration_name
    iteration_dir.mkdir(parents=True, exist_ok=True)

    eval_resolution = resolve_package_evals(package_path)
    selected_evals = _filter_evals(
        list(eval_resolution["data"].get("evals", [])),
        eval_ids=eval_ids,
        max_evals=max_evals,
    )

    package_meta = _load_json(package_path / "metadata" / "package.json")
    summary_rows: list[dict[str, Any]] = []

    for eval_item in selected_evals:
        eval_dir = iteration_dir / _eval_dir_name(eval_item)
        with_skill_dir = eval_dir / "with_skill"
        without_skill_dir = eval_dir / "without_skill"
        judge_dir = eval_dir / "judge"
        with_skill_dir.mkdir(parents=True, exist_ok=True)
        without_skill_dir.mkdir(parents=True, exist_ok=True)
        turns = _turns_for_eval(eval_item)
        eval_metadata = _build_eval_metadata(eval_item, eval_dir.name)
        _write_json(eval_dir / "eval_metadata.json", eval_metadata)

        with_skill_host = KimiCodeHost(session_root=with_skill_dir / "session", timeout_seconds=timeout_seconds)
        with_skill_session = with_skill_host.prepare_session(package_path, eval_item)
        for turn in turns:
            with_skill_host.send_user_turn(with_skill_session, turn)
        with_skill_transcript = with_skill_host.read_transcript(with_skill_session)
        with_skill_response = str(with_skill_transcript.get("turns", [{}])[-1].get("assistant_text", "")).strip()
        _write_json(with_skill_dir / "host-transcript.json", with_skill_transcript)
        _write_text(with_skill_dir / "final_response.md", with_skill_response)
        with_skill_grading = grade_response_text(
            with_skill_response,
            eval_metadata,
            output_file=str(with_skill_dir / "final_response.md"),
        )
        _write_json(with_skill_dir / "grading.json", with_skill_grading)

        without_skill_transcript = _run_plain_kimi_turns(
            turns,
            session_dir=without_skill_dir / "session",
            timeout_seconds=timeout_seconds,
        )
        without_skill_response = str(without_skill_transcript.get("turns", [{}])[-1].get("assistant_text", "")).strip()
        _write_json(without_skill_dir / "host-transcript.json", without_skill_transcript)
        _write_text(without_skill_dir / "final_response.md", without_skill_response)
        without_skill_grading = grade_response_text(
            without_skill_response,
            eval_metadata,
            output_file=str(without_skill_dir / "final_response.md"),
        )
        _write_json(without_skill_dir / "grading.json", without_skill_grading)

        pairwise = _judge_pairwise_with_kimi(
            user_prompt=str(eval_item.get("prompt", "")),
            with_skill_text=with_skill_response,
            without_skill_text=without_skill_response,
            judge_dir=judge_dir,
            timeout_seconds=timeout_seconds,
            judge_max_chars=judge_max_chars,
        )
        _write_json(eval_dir / "pairwise-judgment.json", pairwise)

        summary_rows.append(
            {
                "eval_id": int(eval_item["id"]),
                "eval_name": eval_dir.name,
                "with_skill_pass_rate": with_skill_grading["summary"]["pass_rate"],
                "without_skill_pass_rate": without_skill_grading["summary"]["pass_rate"],
                "final_winner": pairwise["final_winner"],
                "avg_margin": pairwise["avg_margin"],
                "with_skill_dir": str(with_skill_dir),
                "without_skill_dir": str(without_skill_dir),
            }
        )

    win_count = sum(1 for row in summary_rows if row["final_winner"] == "with_skill")
    loss_count = sum(1 for row in summary_rows if row["final_winner"] == "without_skill")
    tie_count = sum(1 for row in summary_rows if row["final_winner"] == "tie")
    pair_count = len(summary_rows)
    summary = {
        "metadata": {
            "package_name": package_meta.get("package_name", package_path.name),
            "skill_name": package_meta.get("skill_name", package_path.name),
            "iteration_dir": str(iteration_dir),
            "source_mode": eval_resolution["source_mode"],
            "runner": "kimi-cli-differential",
        },
        "rows": summary_rows,
        "summary": {
            "pair_count": pair_count,
            "win_rate": round(win_count / pair_count, 4) if pair_count else 0.0,
            "loss_rate": round(loss_count / pair_count, 4) if pair_count else 0.0,
            "tie_rate": round(tie_count / pair_count, 4) if pair_count else 0.0,
            "avg_margin": round(mean([row["avg_margin"] for row in summary_rows]), 4) if summary_rows else 0.0,
            "with_skill_pass_rate": round(mean([row["with_skill_pass_rate"] for row in summary_rows]), 4)
            if summary_rows
            else 0.0,
            "without_skill_pass_rate": round(mean([row["without_skill_pass_rate"] for row in summary_rows]), 4)
            if summary_rows
            else 0.0,
        },
    }
    _write_json(iteration_dir / "kimi-differential-summary.json", summary)
    markdown_lines = [
        f"# {summary['metadata']['skill_name']} Kimi CLI Differential Summary",
        "",
        f"- Package: `{summary['metadata']['package_name']}`",
        f"- Source mode: `{summary['metadata']['source_mode']}`",
        f"- Pair count: `{summary['summary']['pair_count']}`",
        f"- Win rate: `{summary['summary']['win_rate']}`",
        f"- Loss rate: `{summary['summary']['loss_rate']}`",
        f"- Tie rate: `{summary['summary']['tie_rate']}`",
        f"- Avg margin: `{summary['summary']['avg_margin']}`",
        f"- With-skill mean pass rate: `{summary['summary']['with_skill_pass_rate']}`",
        f"- Without-skill mean pass rate: `{summary['summary']['without_skill_pass_rate']}`",
        "",
        "## Rows",
        "",
    ]
    for row in summary_rows:
        markdown_lines.extend(
            [
                f"### Eval {row['eval_id']} - {row['eval_name']}",
                f"- Final winner: `{row['final_winner']}`",
                f"- Avg margin: `{row['avg_margin']}`",
                f"- With-skill pass rate: `{row['with_skill_pass_rate']}`",
                f"- Without-skill pass rate: `{row['without_skill_pass_rate']}`",
                "",
            ]
        )
    _write_text(iteration_dir / "kimi-differential-summary.md", "\n".join(markdown_lines).strip() + "\n")
    return {
        "iteration_dir": str(iteration_dir),
        "pair_count": pair_count,
        "summary_path": str(iteration_dir / "kimi-differential-summary.json"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Kimi CLI differential eval with with_skill vs without_skill.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory.")
    parser.add_argument("--workspace-dir", required=True, help="Path to the package workspace directory.")
    parser.add_argument("--iteration-name", required=True, help="Output iteration directory name, e.g. kimi-cli-iteration-1.")
    parser.add_argument("--eval-ids", default=None, help="Optional comma-separated eval ids.")
    parser.add_argument("--max-evals", type=int, default=None, help="Optional max eval count.")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Per-turn timeout.")
    parser.add_argument("--judge-max-chars", type=int, default=DEFAULT_JUDGE_MAX_CHARS, help="Max chars per response passed into the Kimi judge prompt.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_kimi_cli_differential_eval(
        args.package_dir,
        args.workspace_dir,
        iteration_name=args.iteration_name,
        eval_ids=_resolve_eval_ids(args.eval_ids),
        max_evals=args.max_evals,
        timeout_seconds=args.timeout_seconds,
        judge_max_chars=args.judge_max_chars,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
