from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from toolchain.common import extract_json_object, load_json
from toolchain.kimi_runtime import CommandRunner
from toolchain.kimi_workspace import load_workspace_json, run_kimi_workspace_task, write_workspace_task


RUBRIC_DIMENSIONS = [
    "Thinking Support",
    "Tradeoff Quality",
    "Actionability",
    "Judgment Preservation",
    "Boundary Safety",
]

DEFAULT_MARGIN = 0.0
DEFAULT_CONFIDENCE = 0.0

Sender = Callable[[dict[str, Any]], dict[str, Any]]


def _read_response(run_dir: Path) -> str:
    grading_path = run_dir / "grading.json"
    if grading_path.exists():
        grading = load_json(grading_path)
        output_file = Path(grading.get("output_file", ""))
        if output_file.exists():
            return output_file.read_text(encoding="utf-8")
    output_file = run_dir / "outputs" / "final_response.md"
    if output_file.exists():
        return output_file.read_text(encoding="utf-8")
    return ""


def _extract_json_object(text: str) -> dict[str, Any]:
    return extract_json_object(text, error_message="Judge response did not contain a JSON object.")


def _clamp_score(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(numeric, 1.0)), 4)


def _normalize_side(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"a", "candidate_a", "candidate a"}:
        return "A"
    if text in {"b", "candidate_b", "candidate b"}:
        return "B"
    if text in {"tie", "equal"}:
        return "tie"
    if text in {"not_comparable", "not comparable"}:
        return "not_comparable"
    return "tie"


def _normalize_winner(side: str, orientation: str) -> str:
    if side in {"tie", "not_comparable"}:
        return side
    if orientation == "forward":
        return "with_skill" if side == "A" else "without_skill"
    if orientation == "reversed":
        return "without_skill" if side == "A" else "with_skill"
    return "with_skill" if side == "A" else "without_skill"


def _normalize_rubric(raw: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for dimension in RUBRIC_DIMENSIONS:
        normalized[dimension] = _normalize_side(raw.get(dimension, "tie"))
    return normalized


def _gate_check(run_dir: Path) -> dict[str, Any]:
    reasons: list[str] = []
    response_text = _read_response(run_dir)
    grading_path = run_dir / "grading.json"
    metrics = {}
    if grading_path.exists():
        metrics = load_json(grading_path).get("execution_metrics", {})

    if not response_text.strip():
        reasons.append("empty_response")
    if int(metrics.get("errors_encountered", 0) or 0) > 0:
        reasons.append("execution_errors")

    return {
        "comparable": len(reasons) == 0,
        "reasons": reasons,
        "response_text": response_text,
    }


def _load_cost(run_dir: Path) -> dict[str, float]:
    timing_path = run_dir / "timing.json"
    timing = load_json(timing_path) if timing_path.exists() else {}
    return {
        "time_seconds": float(timing.get("total_duration_seconds", 0.0) or 0.0),
        "tokens": float(timing.get("total_tokens", 0) or 0),
    }


def _build_packet(
    *,
    prompt: str,
    eval_id: int,
    eval_name: str,
    run_number: int,
    orientation: str,
    candidate_a: dict[str, Any],
    candidate_b: dict[str, Any],
) -> dict[str, Any]:
    return {
        "eval_id": eval_id,
        "eval_name": eval_name,
        "run_number": run_number,
        "orientation": orientation,
        "task_prompt": prompt,
        "rubric": RUBRIC_DIMENSIONS,
        "comparison_rules": [
            "Judge user value, not verbosity or formatting polish.",
            "Allow diverse answers if both are genuinely helpful.",
            "Return tie when neither answer is clearly better.",
            "Do not reveal or assume which answer used the skill.",
        ],
        "candidate_a": candidate_a,
        "candidate_b": candidate_b,
    }


def _build_messages(packet: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a strict pairwise judge for AI assistant answers. "
                "Compare Candidate A and Candidate B only on user value. "
                "Return only JSON with keys: winner, margin, confidence, reasoning_summary, rubric_winner_by_dimension. "
                "winner must be one of: A, B, tie. "
                "margin and confidence must be between 0 and 1. "
                "rubric_winner_by_dimension must use only A, B, or tie."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(packet, ensure_ascii=False, indent=2),
        },
    ]


def _workspace_judge_task_markdown() -> str:
    return "\n".join(
        [
            "# Controlled Pairwise Judge Task",
            "",
            "This is a workspace-file task. The terminal reply is only a log line.",
            "",
            "## Inputs",
            "",
            "- Read `inputs/pairwise-packet.json`.",
            "- Compare Candidate A and Candidate B only on user value.",
            "- Do not assume which answer used the skill.",
            "",
            "## Required Output",
            "",
            "Write `outputs/judgment.json` only. It must contain:",
            "",
            "- `winner`: one of `A`, `B`, `tie`",
            "- `margin`: number from 0 to 1",
            "- `confidence`: number from 0 to 1",
            "- `reasoning_summary`: short string",
            "- `rubric_winner_by_dimension`: object whose values are only `A`, `B`, or `tie`",
            "",
            "Do not put the JSON judgment in the terminal response.",
        ]
    )


def _workspace_judge_contract() -> str:
    return "\n".join(
        [
            "# Output Contract",
            "",
            "Required file: `outputs/judgment.json`.",
            "",
            "The file must be a JSON object with keys:",
            "",
            "- `winner`",
            "- `margin`",
            "- `confidence`",
            "- `reasoning_summary`",
            "- `rubric_winner_by_dimension`",
            "",
            "Allowed winner values: `A`, `B`, `tie`.",
            "Terminal output is ignored except as debug log.",
        ]
    )


def _run_workspace_judge(
    packet: dict[str, Any],
    *,
    task_dir: Path,
    judge_model: str | None,
    timeout_seconds: int | None,
    command_runner: CommandRunner | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    required_outputs = ["outputs/judgment.json"]
    write_workspace_task(
        task_dir,
        task_markdown=_workspace_judge_task_markdown(),
        required_outputs=required_outputs,
        contract_markdown=_workspace_judge_contract(),
        inputs={"inputs/pairwise-packet.json": packet},
        metadata={
            "runner": "kimi-code",
            "task_type": "pairwise-judge",
            "eval_id": packet.get("eval_id"),
            "run_number": packet.get("run_number"),
            "orientation": packet.get("orientation"),
        },
    )
    task_result = run_kimi_workspace_task(
        task_dir,
        required_outputs=required_outputs,
        model=judge_model,
        timeout_seconds=timeout_seconds,
        command_runner=command_runner,
    )
    return load_workspace_json(task_result, "outputs/judgment.json"), task_result


def judge_pair(
    *,
    eval_id: int,
    eval_name: str,
    prompt: str,
    run_number: int,
    with_skill_run_dir: str | Path,
    without_skill_run_dir: str | Path,
    orientation: str = "forward",
    sender: Sender | None = None,
    command_runner: CommandRunner | None = None,
    judge_model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    with_skill_path = Path(with_skill_run_dir)
    without_skill_path = Path(without_skill_run_dir)
    with_skill_gate = _gate_check(with_skill_path)
    without_skill_gate = _gate_check(without_skill_path)

    if orientation == "forward":
        candidate_a = {
            "configuration": "with_skill",
            "response": with_skill_gate["response_text"],
            "run_dir": str(with_skill_path),
        }
        candidate_b = {
            "configuration": "without_skill",
            "response": without_skill_gate["response_text"],
            "run_dir": str(without_skill_path),
        }
    else:
        candidate_a = {
            "configuration": "without_skill",
            "response": without_skill_gate["response_text"],
            "run_dir": str(without_skill_path),
        }
        candidate_b = {
            "configuration": "with_skill",
            "response": with_skill_gate["response_text"],
            "run_dir": str(with_skill_path),
        }

    pair_cost = {
        "with_skill": _load_cost(with_skill_path),
        "without_skill": _load_cost(without_skill_path),
    }
    gate_check = {
        "comparable": with_skill_gate["comparable"] and without_skill_gate["comparable"],
        "reasons": sorted(set(with_skill_gate["reasons"] + without_skill_gate["reasons"])),
    }

    result = {
        "metadata": {
            "eval_id": eval_id,
            "eval_name": eval_name,
            "run_number": run_number,
            "orientation": orientation,
            "judge_model": judge_model or "kimi-cli-default",
            "judge_runner": "kimi-code",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "pair": {
            "candidate_a": {"configuration": candidate_a["configuration"], "run_dir": candidate_a["run_dir"]},
            "candidate_b": {"configuration": candidate_b["configuration"], "run_dir": candidate_b["run_dir"]},
        },
        "rubric": RUBRIC_DIMENSIONS,
        "gate_check": gate_check,
        "cost": pair_cost,
        "judgment": {
            "winner": "not_comparable",
            "normalized_winner": "not_comparable",
            "margin": DEFAULT_MARGIN,
            "confidence": DEFAULT_CONFIDENCE,
            "reasoning_summary": "Pair failed gate check and was not judged.",
            "rubric_winner_by_dimension": {dimension: "tie" for dimension in RUBRIC_DIMENSIONS},
        },
    }

    if not gate_check["comparable"]:
        return result

    packet = _build_packet(
        prompt=prompt,
        eval_id=eval_id,
        eval_name=eval_name,
        run_number=run_number,
        orientation=orientation,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
    )
    payload = {
        "model": result["metadata"]["judge_model"],
        "messages": _build_messages(packet),
    }
    if sender is not None:
        raw_response = sender(payload)
        message = raw_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        raw_judgment = _extract_json_object(message)
    else:
        raw_judgment, task_result = _run_workspace_judge(
            packet,
            task_dir=with_skill_path.parent.parent / ".kimi-judge" / f"run-{run_number}-{orientation}",
            judge_model=judge_model,
            timeout_seconds=timeout_seconds,
            command_runner=command_runner,
        )
        raw_response = {
            "choices": [{"message": {"role": "assistant", "content": json.dumps(raw_judgment, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "kimi_workspace_task": {
                "task_dir": task_result.get("work_dir", ""),
                "resolved_outputs": task_result.get("resolved_outputs", {}),
                "terminal_response_policy": "log-only",
                "warnings": task_result.get("warnings", []),
                "stderr": task_result.get("stderr", ""),
            },
        }
    winner = _normalize_side(raw_judgment.get("winner", "tie"))
    rubric = _normalize_rubric(raw_judgment.get("rubric_winner_by_dimension", {}))

    result["judgment"] = {
        "winner": winner,
        "normalized_winner": _normalize_winner(winner, orientation),
        "margin": _clamp_score(raw_judgment.get("margin", DEFAULT_MARGIN)),
        "confidence": _clamp_score(raw_judgment.get("confidence", DEFAULT_CONFIDENCE)),
        "reasoning_summary": str(raw_judgment.get("reasoning_summary", "")).strip(),
        "rubric_winner_by_dimension": rubric,
    }
    return result
