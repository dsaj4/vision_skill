from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.common import is_active_run_dir, load_json

def calculate_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    mean = sum(values) / len(values)
    if len(values) > 1:
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def load_run_results(iteration_dir: Path) -> dict[str, list[dict[str, Any]]]:
    results: dict[str, list[dict[str, Any]]] = {}

    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        metadata = load_json(eval_dir / "eval_metadata.json")
        eval_id = metadata["eval_id"]
        eval_name = metadata.get("eval_name", eval_dir.name)

        for configuration_dir in sorted(eval_dir.iterdir()):
            if not configuration_dir.is_dir() or configuration_dir.name == "__pycache__":
                continue
            configuration = configuration_dir.name
            results.setdefault(configuration, [])

            for run_dir in sorted(configuration_dir.glob("run-*")):
                if not is_active_run_dir(run_dir, iteration_dir):
                    continue
                grading_path = run_dir / "grading.json"
                if not grading_path.exists():
                    continue
                grading = load_json(grading_path)

                timing = grading.get("timing", {})
                timing_path = run_dir / "timing.json"
                if timing_path.exists():
                    timing_data = load_json(timing_path)
                else:
                    timing_data = {}

                metrics = grading.get("execution_metrics", {})
                summary = grading.get("summary", {})

                results[configuration].append(
                    {
                        "eval_id": eval_id,
                        "eval_name": eval_name,
                        "run_number": int(run_dir.name.split("-")[1]),
                        "pass_rate": summary.get("pass_rate", 0.0),
                        "passed": summary.get("passed", 0),
                        "failed": summary.get("failed", 0),
                        "total": summary.get("total", 0),
                        "time_seconds": timing.get("total_duration_seconds", timing_data.get("total_duration_seconds", 0.0)),
                        "tokens": timing_data.get("total_tokens", 0),
                        "tool_calls": metrics.get("total_tool_calls", 0),
                        "errors": metrics.get("errors_encountered", 0),
                        "expectations": grading.get("expectations", []),
                        "notes": [],
                    }
                )

    return results


def aggregate_results(results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    run_summary: dict[str, Any] = {}
    configurations = list(results.keys())

    for configuration, runs in results.items():
        pass_rates = [run["pass_rate"] for run in runs]
        times = [run["time_seconds"] for run in runs]
        tokens = [run["tokens"] for run in runs]
        run_summary[configuration] = {
            "pass_rate": calculate_stats(pass_rates),
            "time_seconds": calculate_stats(times),
            "tokens": calculate_stats(tokens),
        }

    if len(configurations) >= 2:
        primary = run_summary[configurations[0]]
        baseline = run_summary[configurations[1]]
    elif configurations:
        primary = run_summary[configurations[0]]
        baseline = {
            "pass_rate": {"mean": 0.0},
            "time_seconds": {"mean": 0.0},
            "tokens": {"mean": 0.0},
        }
    else:
        primary = baseline = {
            "pass_rate": {"mean": 0.0},
            "time_seconds": {"mean": 0.0},
            "tokens": {"mean": 0.0},
        }

    run_summary["delta"] = {
        "pass_rate": f"{primary['pass_rate']['mean'] - baseline['pass_rate']['mean']:+.2f}",
        "time_seconds": f"{primary['time_seconds']['mean'] - baseline['time_seconds']['mean']:+.1f}",
        "tokens": f"{primary['tokens']['mean'] - baseline['tokens']['mean']:+.0f}",
    }

    return run_summary


def generate_benchmark(iteration_dir: Path, skill_name: str = "", skill_path: str = "") -> dict[str, Any]:
    results = load_run_results(iteration_dir)
    run_summary = aggregate_results(results)
    runs: list[dict[str, Any]] = []

    for configuration, config_runs in results.items():
        for result in config_runs:
            runs.append(
                {
                    "eval_id": result["eval_id"],
                    "eval_name": result["eval_name"],
                    "configuration": configuration,
                    "run_number": result["run_number"],
                    "result": {
                        "pass_rate": result["pass_rate"],
                        "passed": result["passed"],
                        "failed": result["failed"],
                        "total": result["total"],
                        "time_seconds": result["time_seconds"],
                        "tokens": result["tokens"],
                        "tool_calls": result["tool_calls"],
                        "errors": result["errors"],
                    },
                    "expectations": result["expectations"],
                    "notes": result["notes"],
                }
            )

    return {
        "metadata": {
            "skill_name": skill_name or "<skill-name>",
            "skill_path": skill_path or "<skill-path>",
            "executor_model": "<model-name>",
            "analyzer_model": "<model-name>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": sorted({run["eval_id"] for run in runs}),
            "runs_per_configuration": max((run["run_number"] for run in runs), default=0),
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": [],
    }


def generate_markdown(benchmark: dict[str, Any]) -> str:
    metadata = benchmark["metadata"]
    summary = benchmark["run_summary"]
    configs = [key for key in summary.keys() if key != "delta"]
    first = configs[0] if len(configs) >= 1 else "with_skill"
    second = configs[1] if len(configs) >= 2 else "without_skill"

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Date**: {metadata['timestamp']}",
        "",
        "## Summary",
        "",
        f"| Metric | {first.replace('_', ' ').title()} | {second.replace('_', ' ').title()} | Delta |",
        "|--------|---------------------------|------------------------------|-------|",
    ]

    lines.append(
        f"| Pass Rate | {summary.get(first, {}).get('pass_rate', {}).get('mean', 0):.2f} | "
        f"{summary.get(second, {}).get('pass_rate', {}).get('mean', 0):.2f} | {summary.get('delta', {}).get('pass_rate', 'N/A')} |"
    )
    lines.append(
        f"| Time | {summary.get(first, {}).get('time_seconds', {}).get('mean', 0):.1f}s | "
        f"{summary.get(second, {}).get('time_seconds', {}).get('mean', 0):.1f}s | {summary.get('delta', {}).get('time_seconds', 'N/A')} |"
    )
    lines.append(
        f"| Tokens | {summary.get(first, {}).get('tokens', {}).get('mean', 0):.0f} | "
        f"{summary.get(second, {}).get('tokens', {}).get('mean', 0):.0f} | {summary.get('delta', {}).get('tokens', 'N/A')} |"
    )

    return "\n".join(lines)
