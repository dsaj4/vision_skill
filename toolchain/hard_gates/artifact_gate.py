from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.common import load_json, write_json, write_text


REQUIRED_RUN_ARTIFACTS = [
    "request.json",
    "raw_response.json",
    "transcript.json",
    "timing.json",
    "outputs/final_response.md",
    "outputs/latest_assistant_response.md",
]

REQUIRED_CONFIGURATIONS = ["with_skill", "without_skill"]


def _load_eval_metadata(eval_dir: Path) -> dict[str, Any]:
    path = eval_dir / "eval_metadata.json"
    if not path.exists():
        return {
            "eval_id": None,
            "eval_name": eval_dir.name,
        }
    return load_json(path)


def _run_number(run_dir: Path) -> int:
    try:
        return int(run_dir.name.split("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def _check_run(run_dir: Path, eval_metadata: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    missing = [relative for relative in REQUIRED_RUN_ARTIFACTS if not (run_dir / relative).exists()]
    if missing:
        blockers.extend(f"missing:{item}" for item in missing)

    error_path = run_dir / "execution_error.json"
    execution_error = load_json(error_path) if error_path.exists() else {}
    if execution_error:
        blockers.append("execution_error")

    output_path = run_dir / "outputs" / "final_response.md"
    output_text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    if output_path.exists() and not output_text.strip():
        blockers.append("empty_final_response")

    latest_output_path = run_dir / "outputs" / "latest_assistant_response.md"
    latest_output_text = latest_output_path.read_text(encoding="utf-8") if latest_output_path.exists() else ""
    if latest_output_path.exists() and not latest_output_text.strip():
        blockers.append("empty_latest_assistant_response")

    timing_path = run_dir / "timing.json"
    timing = load_json(timing_path) if timing_path.exists() else {}
    if timing_path.exists() and float(timing.get("total_duration_seconds", 0.0) or 0.0) < 0:
        blockers.append("invalid_timing")

    return {
        "eval_id": eval_metadata.get("eval_id"),
        "eval_name": eval_metadata.get("eval_name", ""),
        "configuration": run_dir.parent.name,
        "run_number": _run_number(run_dir),
        "run_dir": str(run_dir),
        "output_file": str(output_path),
        "passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def _check_eval(eval_dir: Path, eval_metadata: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    run_counts: dict[str, int] = {}
    for configuration in REQUIRED_CONFIGURATIONS:
        config_dir = eval_dir / configuration
        if not config_dir.exists():
            blockers.append(f"missing_configuration:{configuration}")
            run_counts[configuration] = 0
            continue
        runs = [path for path in config_dir.glob("run-*") if path.is_dir()]
        run_counts[configuration] = len(runs)
        if not runs:
            blockers.append(f"no_runs:{configuration}")

    non_zero_counts = {count for count in run_counts.values() if count > 0}
    if len(non_zero_counts) > 1:
        blockers.append("run_count_mismatch")

    return {
        "eval_id": eval_metadata.get("eval_id"),
        "eval_name": eval_metadata.get("eval_name", eval_dir.name),
        "eval_dir": str(eval_dir),
        "run_counts": run_counts,
        "passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def run_hard_gate(iteration_dir: str | Path) -> dict[str, Any]:
    """Validate that an iteration has the minimum artifacts needed for deep eval.

    Hard gates intentionally avoid judging quality. They only answer whether the
    raw run evidence is complete enough for downstream evaluators.
    """

    iteration_path = Path(iteration_dir)
    per_run: list[dict[str, Any]] = []
    per_eval: list[dict[str, Any]] = []
    for eval_dir in sorted(iteration_path.glob("eval-*")):
        if not eval_dir.is_dir():
            continue
        eval_metadata = _load_eval_metadata(eval_dir)
        per_eval.append(_check_eval(eval_dir, eval_metadata))
        for configuration_dir in sorted(eval_dir.iterdir()):
            if not configuration_dir.is_dir() or configuration_dir.name.startswith("."):
                continue
            for run_dir in sorted(configuration_dir.glob("run-*")):
                if run_dir.is_dir():
                    per_run.append(_check_run(run_dir, eval_metadata))

    blocker_counts: dict[str, int] = {}
    for run in per_run:
        for blocker in run["blockers"]:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1

    failed_runs = [run for run in per_run if not run["passed"]]
    failed_evals = [item for item in per_eval if not item["passed"]]
    if not per_eval:
        blocker_counts["no_eval_dirs"] = blocker_counts.get("no_eval_dirs", 0) + 1
    for item in failed_evals:
        for blocker in item["blockers"]:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    report = {
        "metadata": {
            "iteration_dir": str(iteration_path),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gate_type": "readiness-only",
            "quality_policy": "does-not-score-quality",
            "eval_count": len(per_eval),
            "run_count": len(per_run),
            "passed_run_count": len(per_run) - len(failed_runs),
            "failed_run_count": len(failed_runs),
            "failed_eval_count": len(failed_evals),
        },
        "passed": bool(per_eval) and bool(per_run) and not failed_runs and not failed_evals,
        "blockers": sorted(blocker_counts),
        "blocker_counts": blocker_counts,
        "per_eval": per_eval,
        "per_run": per_run,
    }
    write_hard_gate_artifacts(iteration_path, report)
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hard Gate Report",
        "",
        f"**Generated At**: {report['metadata']['generated_at']}",
        f"**Passed**: {report['passed']}",
        "",
        "## Summary",
        "",
        f"- Evals: {report['metadata']['eval_count']}",
        f"- Runs: {report['metadata']['run_count']}",
        f"- Passed runs: {report['metadata']['passed_run_count']}",
        f"- Failed runs: {report['metadata']['failed_run_count']}",
        f"- Blockers: {', '.join(report['blockers']) if report['blockers'] else 'none'}",
        "",
        "## Failed Evals",
        "",
    ]
    failed_evals = [item for item in report["per_eval"] if not item["passed"]]
    if not failed_evals:
        lines.append("- none")
    else:
        for item in failed_evals:
            lines.append(
                f"- Eval {item['eval_id']}: {', '.join(item['blockers'])}"
            )
    lines.extend(
        [
            "",
            "## Failed Runs",
            "",
        ]
    )
    failed = [run for run in report["per_run"] if not run["passed"]]
    if not failed:
        lines.append("- none")
    else:
        for run in failed:
            lines.append(
                f"- Eval {run['eval_id']} / {run['configuration']} / run-{run['run_number']}: "
                f"{', '.join(run['blockers'])}"
            )
    return "\n".join(lines).strip() + "\n"


def write_hard_gate_artifacts(iteration_dir: str | Path, report: dict[str, Any]) -> dict[str, str]:
    iteration_path = Path(iteration_dir)
    json_path = iteration_path / "hard-gate.json"
    markdown_path = iteration_path / "hard-gate.md"
    write_json(json_path, report)
    write_text(markdown_path, _markdown(report))
    return {
        "hard_gate_json": str(json_path),
        "hard_gate_markdown": str(markdown_path),
    }
