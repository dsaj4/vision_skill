from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Sequence

from toolchain.common import load_json, parse_eval_ids
from toolchain.benchmarks.iteration_scaffold import prepare_iteration
from toolchain.deep_evals.run_deep_eval import run_deep_eval
from toolchain.eval_factory.sync import sync_package_evals
from toolchain.executors.kimi_code_executor import execute_iteration
from toolchain.hard_gates.artifact_gate import run_hard_gate
from toolchain.judges.pairwise_judge import Sender as JudgeSender
from toolchain.kimi_runtime import CommandRunner
from toolchain.package_snapshot import snapshot_package_state
from toolchain.quantitative.run_quantitative_bundle import run_quantitative_bundle
from toolchain.reviews.cognitive_review import (
    build_human_review_packet,
    generate_release_recommendation,
    write_human_review_authorization_template,
)


def _resolve_runs_per_configuration(runs_per_configuration: int | None, thorough: bool) -> int:
    if runs_per_configuration is not None:
        return int(runs_per_configuration)
    if thorough:
        return 3
    return 1


def _resolve_max_evals(max_evals: int | None, eval_ids: list[int] | None, smoke: bool) -> int | None:
    if max_evals is not None:
        return int(max_evals)
    if smoke and not eval_ids:
        return 2
    return None


def _resolve_smoke_model(explicit_model: str | None, env_key: str, fallback_model: str | None) -> str | None:
    if explicit_model:
        return explicit_model
    env_value = os.getenv(env_key)
    if env_value:
        return env_value
    return fallback_model


def run_eval_pipeline(
    package_dir: str | Path,
    workspace_dir: str | Path,
    *,
    iteration_number: int,
    runs_per_configuration: int | None = None,
    command_runner: CommandRunner | None = None,
    judge_sender: JudgeSender | None = None,
    analyzer_sender: JudgeSender | None = None,
    model: str | None = None,
    judge_model: str | None = None,
    analyzer_model: str | None = None,
    timeout_seconds: int | None = None,
    refresh_review_template: bool = False,
    stop_on_error: bool = False,
    smoke: bool = False,
    thorough: bool = False,
    balanced_judging: bool = False,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
    skip_completed: bool = False,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    package_meta = load_json(package_path / "metadata" / "package.json")
    skill_name = package_meta.get("skill_name", package_path.name)
    effective_runs_per_configuration = _resolve_runs_per_configuration(runs_per_configuration, thorough)
    effective_max_evals = _resolve_max_evals(max_evals, eval_ids, smoke)
    effective_skip_completed = skip_completed or smoke
    effective_balanced_judging = balanced_judging or thorough
    effective_judge_model = _resolve_smoke_model(judge_model, "VISION_SMOKE_JUDGE_MODEL", model)
    effective_analyzer_model = _resolve_smoke_model(analyzer_model, "VISION_SMOKE_ANALYZER_MODEL", model)

    sync_result = sync_package_evals(package_path)
    prepare_result = prepare_iteration(
        package_path,
        workspace_path,
        iteration_number=iteration_number,
        runs_per_configuration=effective_runs_per_configuration,
        eval_ids=eval_ids,
        max_evals=effective_max_evals,
    )
    iteration_path = Path(prepare_result["iteration_dir"])
    package_snapshot = snapshot_package_state(package_path, iteration_path, workspace_dir=workspace_path)

    execute_result = execute_iteration(
        iteration_path,
        package_path,
        command_runner=command_runner,
        model=model,
        timeout_seconds=timeout_seconds,
        stop_on_error=stop_on_error,
        skip_completed=effective_skip_completed,
    )

    hard_gate = run_hard_gate(iteration_path)
    if stop_on_error and not hard_gate["passed"]:
        raise RuntimeError("Hard gate failed: " + ", ".join(hard_gate.get("blockers", [])))

    quantitative_result = run_quantitative_bundle(
        iteration_path,
        package_path,
        skill_name=skill_name,
        sender=judge_sender,
        command_runner=command_runner,
        judge_model=effective_judge_model,
        timeout_seconds=timeout_seconds,
        balanced_judging=effective_balanced_judging,
    )

    deep_eval_result = run_deep_eval(
        iteration_path,
        package_path,
        sender=analyzer_sender,
        command_runner=command_runner,
        deep_eval_model=effective_analyzer_model,
        timeout_seconds=timeout_seconds,
    )
    review_packet = build_human_review_packet(
        iteration_path,
        package_path,
        sender=analyzer_sender,
        command_runner=command_runner,
        review_model=effective_analyzer_model,
        timeout_seconds=timeout_seconds,
    )
    review_path = iteration_path / "human-review-authorization.json"
    legacy_review_path = iteration_path / "human-review-score.json"
    review_template_written = False
    if refresh_review_template or (not review_path.exists() and not legacy_review_path.exists()):
        write_human_review_authorization_template(iteration_path, package_name=package_path.name)
        review_template_written = True
    recommendation = generate_release_recommendation(iteration_path)

    return {
        "package_dir": str(package_path),
        "workspace_dir": str(workspace_path),
        "iteration_dir": str(iteration_path),
        "eval_source_mode": prepare_result.get("eval_source_mode", sync_result.get("source_mode", "package-local")),
        "smoke_mode": smoke,
        "thorough_mode": thorough,
        "runs_per_configuration": effective_runs_per_configuration,
        "judge_strategy": "balanced" if effective_balanced_judging else "single",
        "selected_eval_ids": prepare_result["selected_eval_ids"],
        "selected_eval_count": prepare_result["selected_eval_count"],
        "skip_completed": effective_skip_completed,
        "completed_runs": execute_result["completed_runs"],
        "skipped_runs": execute_result["skipped_runs"],
        "inactive_runs": execute_result.get("inactive_runs", []),
        "failed_runs": execute_result["failed_runs"],
        "hard_gate_passed": hard_gate["passed"],
        "quality_primary_mode": deep_eval_result["deep_eval"]["metadata"]["quality_primary_mode"],
        "recommendation": recommendation["recommendation"],
        "blockers": recommendation["blockers"],
        "level3_primary_mode": quantitative_result["level3_summary"]["primary_mode"],
        "review_template_written": review_template_written,
        "review_authorization_template_written": review_template_written,
        "artifacts": {
            "hard_gate_json": str(iteration_path / "hard-gate.json"),
            "hard_gate_markdown": str(iteration_path / "hard-gate.md"),
            "benchmark_json": quantitative_result["artifacts"]["benchmark_json"],
            "benchmark_markdown": quantitative_result["artifacts"]["benchmark_markdown"],
            "differential_benchmark_json": str(iteration_path / "differential-benchmark.json"),
            "differential_benchmark_markdown": str(iteration_path / "differential-benchmark.md"),
            "level3_summary_json": quantitative_result["artifacts"]["level3_summary_json"],
            "level3_summary_markdown": quantitative_result["artifacts"]["level3_summary_markdown"],
            "stability_json": quantitative_result["artifacts"]["stability_json"],
            "quantitative_summary_json": quantitative_result["artifacts"]["quantitative_summary_json"],
            "quantitative_summary_markdown": quantitative_result["artifacts"]["quantitative_summary_markdown"],
            "deep_eval_json": deep_eval_result["artifacts"]["deep_eval_json"],
            "deep_eval_markdown": deep_eval_result["artifacts"]["deep_eval_markdown"],
            "quality_failure_tags_json": deep_eval_result["artifacts"]["quality_failure_tags_json"],
            "agent_review_report_json": str(iteration_path / "agent-review-report.json"),
            "human_review_packet": str(iteration_path / "human-review-packet.md"),
            "human_review_authorization": str(iteration_path / "human-review-authorization.json"),
            "release_recommendation": str(iteration_path / "release-recommendation.json"),
            "iteration_package_snapshot_dir": package_snapshot["iteration_snapshot_dir"],
            "iteration_package_manifest": package_snapshot["iteration_manifest"],
            "latest_package_dir": package_snapshot["latest_package_dir"],
            "latest_package_manifest": package_snapshot["latest_package_manifest"],
            "latest_skill_markdown": package_snapshot["latest_skill_markdown"],
            "upload_ready_root": package_snapshot["upload_ready_root"],
            "upload_ready_index": package_snapshot["upload_ready_index"],
            "upload_ready_package_dir": package_snapshot["upload_ready_package_dir"],
            "upload_ready_skill_markdown": package_snapshot["upload_ready_skill_markdown"],
        },
        "review_summary": review_packet["summary"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the full Vision Skill eval pipeline.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory.")
    parser.add_argument("--workspace-dir", required=True, help="Path to the package workspace directory.")
    parser.add_argument("--iteration-number", type=int, required=True, help="Iteration number to prepare and run.")
    parser.add_argument("--runs-per-configuration", type=int, default=None, help="Number of runs for each with_skill / without_skill configuration. Defaults to 1. Use --thorough for 3.")
    parser.add_argument("--model", default=None, help="Optional execution model override.")
    parser.add_argument("--judge-model", default=None, help="Optional judge model override.")
    parser.add_argument("--analyzer-model", default=None, help="Optional analyzer model override.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional timeout override.")
    parser.add_argument("--refresh-review-template", action="store_true", help="Overwrite any existing human review authorization template.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop immediately when a run execution fails.")
    parser.add_argument("--smoke", action="store_true", help="Run a lightweight smoke path: default 1 run per configuration, max 2 evals, and skip completed runs.")
    parser.add_argument("--thorough", action="store_true", help="Run the slower stability-oriented profile: default 3 runs per configuration and balanced pairwise judging.")
    parser.add_argument("--balanced-judging", action="store_true", help="Use forward + reversed pairwise judging, with optional tiebreak, instead of the default single-pass judge.")
    parser.add_argument("--max-evals", type=int, default=None, help="Optional limit for how many evals to include in this iteration.")
    parser.add_argument("--eval-ids", default=None, help="Optional comma-separated eval ids to include, e.g. 101,102.")
    parser.add_argument("--skip-completed", action="store_true", help="Skip runs that already have complete execution artifacts.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_eval_pipeline(
        args.package_dir,
        args.workspace_dir,
        iteration_number=args.iteration_number,
        runs_per_configuration=args.runs_per_configuration,
        model=args.model,
        judge_model=args.judge_model,
        analyzer_model=args.analyzer_model,
        timeout_seconds=args.timeout_seconds,
        refresh_review_template=args.refresh_review_template,
        stop_on_error=args.stop_on_error,
        smoke=args.smoke,
        thorough=args.thorough,
        balanced_judging=args.balanced_judging,
        eval_ids=parse_eval_ids(args.eval_ids),
        max_evals=args.max_evals,
        skip_completed=args.skip_completed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
