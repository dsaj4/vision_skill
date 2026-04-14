from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Sequence

from toolchain.benchmarks.iteration_scaffold import prepare_iteration
from toolchain.benchmarks.level3_summary import generate_level3_summary, write_level3_summary_artifacts
from toolchain.benchmarks.run_benchmark import grade_iteration_runs
from toolchain.benchmarks.run_differential_benchmark import run_differential_benchmark
from toolchain.eval_factory.sync import sync_package_evals
from toolchain.executors.dashscope_executor import Sender as ExecutorSender, execute_iteration
from toolchain.judges.pairwise_judge import Sender as JudgeSender
from toolchain.run_level456 import run_level456


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_eval_ids(value: str | None) -> list[int] | None:
    if not value:
        return None
    items = [part.strip() for part in value.split(",")]
    return [int(item) for item in items if item]


def _resolve_runs_per_configuration(runs_per_configuration: int | None, smoke: bool) -> int:
    if runs_per_configuration is not None:
        return int(runs_per_configuration)
    return 1 if smoke else 3


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
    sender: ExecutorSender | None = None,
    judge_sender: JudgeSender | None = None,
    analyzer_sender: JudgeSender | None = None,
    api_key: str | None = None,
    model: str | None = None,
    judge_model: str | None = None,
    analyzer_model: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: int | None = None,
    refresh_review_template: bool = False,
    stop_on_error: bool = False,
    smoke: bool = False,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
    skip_completed: bool = False,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    package_meta = _load_json(package_path / "metadata" / "package.json")
    skill_name = package_meta.get("skill_name", package_path.name)
    effective_runs_per_configuration = _resolve_runs_per_configuration(runs_per_configuration, smoke)
    effective_max_evals = _resolve_max_evals(max_evals, eval_ids, smoke)
    effective_skip_completed = skip_completed or smoke
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

    execute_result = execute_iteration(
        iteration_path,
        package_path,
        sender=sender,
        api_key=api_key,
        model=model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        stop_on_error=stop_on_error,
        skip_completed=effective_skip_completed,
    )
    benchmark_result = grade_iteration_runs(iteration_path, skill_name=skill_name, skill_path=str(package_path))
    differential_result = run_differential_benchmark(
        iteration_path,
        skill_name=skill_name,
        skill_path=str(package_path),
        sender=judge_sender,
        api_key=api_key,
        judge_model=effective_judge_model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
    )
    level3_summary = generate_level3_summary(iteration_path)
    level3_paths = write_level3_summary_artifacts(iteration_path, level3_summary)
    level456_result = run_level456(
        iteration_path,
        package_path,
        sender=analyzer_sender,
        api_key=api_key,
        analyzer_model=effective_analyzer_model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
        refresh_review_template=refresh_review_template,
    )

    return {
        "package_dir": str(package_path),
        "workspace_dir": str(workspace_path),
        "iteration_dir": str(iteration_path),
        "eval_source_mode": prepare_result.get("eval_source_mode", sync_result.get("source_mode", "package-local")),
        "smoke_mode": smoke,
        "runs_per_configuration": effective_runs_per_configuration,
        "selected_eval_ids": prepare_result["selected_eval_ids"],
        "selected_eval_count": prepare_result["selected_eval_count"],
        "skip_completed": effective_skip_completed,
        "completed_runs": execute_result["completed_runs"],
        "skipped_runs": execute_result["skipped_runs"],
        "failed_runs": execute_result["failed_runs"],
        "recommendation": level456_result["recommendation"],
        "blockers": level456_result["blockers"],
        "level3_primary_mode": level3_summary["primary_mode"],
        "artifacts": {
            "benchmark_json": benchmark_result["benchmark_path"],
            "benchmark_markdown": benchmark_result["benchmark_markdown_path"],
            "differential_benchmark_json": str(iteration_path / "differential-benchmark.json"),
            "differential_benchmark_markdown": str(iteration_path / "differential-benchmark.md"),
            "level3_summary_json": level3_paths["level3_summary_json"],
            "level3_summary_markdown": level3_paths["level3_summary_markdown"],
            "stability_json": level456_result["artifacts"]["stability_json"],
            "analysis_json": level456_result["artifacts"]["analysis_json"],
            "human_review_packet": level456_result["artifacts"]["human_review_packet"],
            "release_recommendation": level456_result["artifacts"]["release_recommendation"],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the full Vision Skill eval pipeline.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory.")
    parser.add_argument("--workspace-dir", required=True, help="Path to the package workspace directory.")
    parser.add_argument("--iteration-number", type=int, required=True, help="Iteration number to prepare and run.")
    parser.add_argument("--runs-per-configuration", type=int, default=None, help="Number of runs for each with_skill / without_skill configuration. Defaults to 3, or 1 in --smoke mode.")
    parser.add_argument("--model", default=None, help="Optional execution model override.")
    parser.add_argument("--judge-model", default=None, help="Optional judge model override.")
    parser.add_argument("--analyzer-model", default=None, help="Optional analyzer model override.")
    parser.add_argument("--api-key", default=None, help="Optional DashScope API key override.")
    parser.add_argument("--endpoint", default=None, help="Optional endpoint override.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional timeout override.")
    parser.add_argument("--refresh-review-template", action="store_true", help="Overwrite any existing human review score template.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop immediately when a run execution fails.")
    parser.add_argument("--smoke", action="store_true", help="Run a lightweight smoke path: default 1 run per configuration, max 2 evals, and skip completed runs.")
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
        api_key=args.api_key,
        model=args.model,
        judge_model=args.judge_model,
        analyzer_model=args.analyzer_model,
        endpoint=args.endpoint,
        timeout_seconds=args.timeout_seconds,
        refresh_review_template=args.refresh_review_template,
        stop_on_error=args.stop_on_error,
        smoke=args.smoke,
        eval_ids=_resolve_eval_ids(args.eval_ids),
        max_evals=args.max_evals,
        skip_completed=args.skip_completed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
