from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.benchmarks.level3_summary import ensure_level3_summary
from toolchain.common import is_active_run_dir, load_json, write_json, write_text


PAUSE_MARKERS = ['回复"继续"', '回复"不对"', '回复"直接要结果"', "输出后暂停", "暂停确认"]
SWOT_GROUPS = [
    ("strengths", "优势"),
    ("weaknesses", "劣势"),
    ("opportunities", "机会"),
    ("threats", "威胁"),
]


def _calculate_stats(values: list[float]) -> dict[str, float]:
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


def _length_bucket(char_count: int) -> str:
    if char_count < 600:
        return "short"
    if char_count < 1500:
        return "medium"
    return "long"


def _fingerprint_response(response_text: str) -> dict[str, Any]:
    response_lower = response_text.lower()
    heading_count = len(re.findall(r"^#{1,6}\s+", response_text, re.MULTILINE))
    quadrant_hits = {
        label: any(keyword.lower() in response_lower for keyword in group)
        for label, group in (
            ("strengths", SWOT_GROUPS[0]),
            ("weaknesses", SWOT_GROUPS[1]),
            ("opportunities", SWOT_GROUPS[2]),
            ("threats", SWOT_GROUPS[3]),
        )
    }
    pause_marker_hit = any(marker.lower() in response_lower for marker in PAUSE_MARKERS)
    direct_result_mode = all(quadrant_hits.values()) and not pause_marker_hit
    char_count = len(response_text)

    return {
        "heading_count": heading_count,
        "quadrant_hits": quadrant_hits,
        "pause_marker_hit": pause_marker_hit,
        "direct_result_mode": direct_result_mode,
        "length_bucket": _length_bucket(char_count),
        "char_count": char_count,
    }


def _fingerprint_key(fingerprint: dict[str, Any]) -> str:
    quadrants = "".join("1" if fingerprint["quadrant_hits"][name] else "0" for name in ("strengths", "weaknesses", "opportunities", "threats"))
    return "|".join(
        [
            f"h{fingerprint['heading_count']}",
            f"q{quadrants}",
            f"p{int(fingerprint['pause_marker_hit'])}",
            f"d{int(fingerprint['direct_result_mode'])}",
            f"l{fingerprint['length_bucket']}",
        ]
    )


def _load_iteration_runs(iteration_dir: Path) -> dict[str, Any]:
    evals: list[dict[str, Any]] = []
    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        eval_metadata = load_json(eval_dir / "eval_metadata.json")
        eval_item = {
            "eval_id": eval_metadata["eval_id"],
            "eval_name": eval_metadata.get("eval_name", eval_dir.name),
            "configurations": {},
        }
        for configuration_dir in sorted(eval_dir.iterdir()):
            if not configuration_dir.is_dir() or configuration_dir.name == "__pycache__":
                continue
            runs: list[dict[str, Any]] = []
            for run_dir in sorted(configuration_dir.glob("run-*")):
                if not is_active_run_dir(run_dir, iteration_dir):
                    continue
                grading_path = run_dir / "grading.json"
                if not grading_path.exists():
                    continue
                grading = load_json(grading_path)
                timing_path = run_dir / "timing.json"
                timing = load_json(timing_path) if timing_path.exists() else grading.get("timing", {})
                output_file = Path(grading["output_file"])
                response_text = output_file.read_text(encoding="utf-8")
                fingerprint = _fingerprint_response(response_text)
                runs.append(
                    {
                        "run_number": int(run_dir.name.split("-")[1]),
                        "path": str(run_dir),
                        "summary": grading.get("summary", {}),
                        "timing": timing,
                        "expectations": grading.get("expectations", []),
                        "fingerprint": fingerprint,
                        "fingerprint_key": _fingerprint_key(fingerprint),
                    }
                )
            if runs:
                eval_item["configurations"][configuration_dir.name] = runs
        evals.append(eval_item)
    return {"evals": evals}


def _build_expectation_variance(runs: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for run in runs:
        for expectation in run.get("expectations", []):
            expectation_id = expectation.get("id") or expectation.get("text", "unnamed")
            record = grouped.setdefault(
                expectation_id,
                {
                    "text": expectation.get("text", expectation_id),
                    "passed_runs": 0,
                    "total_runs": 0,
                    "failures": [],
                },
            )
            passed = bool(expectation.get("passed"))
            record["total_runs"] += 1
            if passed:
                record["passed_runs"] += 1
            else:
                record["failures"].append(expectation.get("evidence", ""))

    result: dict[str, Any] = {}
    for expectation_id, record in grouped.items():
        total_runs = record["total_runs"]
        pass_rate = round(record["passed_runs"] / total_runs, 4) if total_runs else 0.0
        result[expectation_id] = {
            "text": record["text"],
            "passed_runs": record["passed_runs"],
            "total_runs": total_runs,
            "pass_rate": pass_rate,
            "unstable": 0.0 < pass_rate < 1.0,
            "failures": record["failures"],
        }
    return result


def _summarize_configuration(runs: list[dict[str, Any]]) -> dict[str, Any]:
    pass_rates = [float(run["summary"].get("pass_rate", 0.0)) for run in runs]
    times = [float(run["timing"].get("total_duration_seconds", 0.0)) for run in runs]
    tokens = [float(run["timing"].get("total_tokens", 0.0)) for run in runs]
    fingerprints = [run["fingerprint_key"] for run in runs]
    expectation_variance = _build_expectation_variance(runs)

    return {
        "pass_rate": _calculate_stats(pass_rates),
        "time_seconds": _calculate_stats(times),
        "tokens": _calculate_stats(tokens),
        "expectation_variance": expectation_variance,
        "drift": {
            "drift_detected": len(set(fingerprints)) > 1,
            "unique_fingerprint_count": len(set(fingerprints)),
            "fingerprints": fingerprints,
        },
    }


def _pairwise_index(level3_summary: dict[str, Any]) -> dict[tuple[int, int], dict[str, Any]]:
    return {
        (int(item["eval_id"]), int(item["run_number"])): item
        for item in level3_summary.get("per_eval", [])
        if item.get("eval_id") is not None and item.get("run_number") is not None
    }


def _overall_from_per_eval(per_eval: list[dict[str, Any]], level3_summary: dict[str, Any]) -> dict[str, Any]:
    aggregated: dict[str, dict[str, list[float]]] = {}
    flags: list[str] = []

    for item in per_eval:
        for configuration, summary in item["configurations"].items():
            target = aggregated.setdefault(configuration, {"pass_rate": [], "time_seconds": [], "tokens": []})
            target["pass_rate"].append(summary["pass_rate"]["mean"])
            target["time_seconds"].append(summary["time_seconds"]["mean"])
            target["tokens"].append(summary["tokens"]["mean"])
        flags.extend(item["flags"])

    configurations_summary: dict[str, Any] = {}
    for configuration, metrics in aggregated.items():
        configurations_summary[configuration] = {
            "pass_rate": _calculate_stats(metrics["pass_rate"]),
            "time_seconds": _calculate_stats(metrics["time_seconds"]),
            "tokens": _calculate_stats(metrics["tokens"]),
        }

    with_std = configurations_summary.get("with_skill", {}).get("pass_rate", {}).get("stddev", 0.0)
    without_std = configurations_summary.get("without_skill", {}).get("pass_rate", {}).get("stddev", 0.0)
    if with_std - without_std >= 0.15:
        flags.append("instability_risk")

    pairwise = level3_summary.get("pairwise_summary", {})
    if float(pairwise.get("win_rate", 0.0) or 0.0) <= 0.5 and float(pairwise.get("cost_adjusted_value", 0.0) or 0.0) <= 0.0:
        flags.append("weak_stability_value")
    if float(pairwise.get("judge_disagreement_rate", 0.0) or 0.0) >= 0.25:
        flags.append("instability_risk")

    return {
        "configurations": configurations_summary,
        "flags": sorted(set(flags)),
    }


def _variance_by_expectation(per_eval: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for eval_item in per_eval:
        for configuration, summary in eval_item["configurations"].items():
            for expectation_id, variance in summary["expectation_variance"].items():
                items.append(
                    {
                        "eval_id": eval_item["eval_id"],
                        "eval_name": eval_item["eval_name"],
                        "configuration": configuration,
                        "expectation_id": expectation_id,
                        "text": variance["text"],
                        "passed_runs": variance["passed_runs"],
                        "total_runs": variance["total_runs"],
                        "pass_rate": variance["pass_rate"],
                        "unstable": variance["unstable"],
                    }
                )
    return {"expectations": items}


def generate_stability_report(iteration_dir: Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    level3_summary = ensure_level3_summary(iteration_path)
    loaded = _load_iteration_runs(iteration_path)
    pairwise_results = _pairwise_index(level3_summary)

    per_eval: list[dict[str, Any]] = []
    runs_per_configuration = 0
    for eval_item in loaded["evals"]:
        config_summaries: dict[str, Any] = {}
        flags: list[str] = []
        eval_pairwise: list[dict[str, Any]] = []

        for configuration, runs in eval_item["configurations"].items():
            runs_per_configuration = max(runs_per_configuration, len(runs))
            summary = _summarize_configuration(runs)
            config_summaries[configuration] = summary
            if any(item["unstable"] for item in summary["expectation_variance"].values()):
                flags.append("unstable")
            if summary["drift"]["drift_detected"]:
                flags.append("drift_detected")
            for run in runs:
                pairwise = pairwise_results.get((int(eval_item["eval_id"]), int(run["run_number"])))
                if pairwise is not None and pairwise not in eval_pairwise:
                    eval_pairwise.append(pairwise)

        if any(item.get("judge_disagreement") for item in eval_pairwise):
            flags.append("instability_risk")
        if eval_pairwise and not any(item.get("final_winner") == "with_skill" for item in eval_pairwise):
            flags.append("weak_stability_value")

        per_eval.append(
            {
                "eval_id": eval_item["eval_id"],
                "eval_name": eval_item["eval_name"],
                "configurations": config_summaries,
                "pairwise_results": eval_pairwise,
                "flags": sorted(set(flags)),
            }
        )

    return {
        "metadata": {
            "iteration_dir": str(iteration_path),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "runs_per_configuration": runs_per_configuration,
            "eval_ids": [item["eval_id"] for item in per_eval],
            "level3_primary_mode": level3_summary.get("primary_mode", "unknown"),
        },
        "level3_summary": {
            "primary_mode": level3_summary.get("primary_mode", "unknown"),
            "pairwise_summary": level3_summary.get("pairwise_summary", {}),
        },
        "per_eval": per_eval,
        "overall": _overall_from_per_eval(per_eval, level3_summary),
        "variance_by_expectation": _variance_by_expectation(per_eval),
    }


def _generate_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Stability Report",
        "",
        f"**Generated At**: {report['metadata']['generated_at']}",
        "",
        "## Level 3",
        "",
        f"- Primary mode: {report['level3_summary']['primary_mode']}",
        f"- Pairwise win rate: {report['level3_summary']['pairwise_summary'].get('win_rate', 0.0):.4f}",
        f"- Pairwise disagreement rate: {report['level3_summary']['pairwise_summary'].get('judge_disagreement_rate', 0.0):.4f}",
        f"- Cost-adjusted value: {report['level3_summary']['pairwise_summary'].get('cost_adjusted_value', 0.0):.4f}",
        "",
        "## Overall",
        "",
        f"- Runs per configuration: {report['metadata']['runs_per_configuration']}",
        f"- Flags: {', '.join(report['overall']['flags']) if report['overall']['flags'] else 'none'}",
        "",
        "| Configuration | Pass Rate Mean | Pass Rate Stddev | Time Mean | Tokens Mean |",
        "|---|---:|---:|---:|---:|",
    ]
    for configuration, summary in report["overall"]["configurations"].items():
        lines.append(
            f"| {configuration} | {summary['pass_rate']['mean']:.4f} | {summary['pass_rate']['stddev']:.4f} | "
            f"{summary['time_seconds']['mean']:.2f}s | {summary['tokens']['mean']:.0f} |"
        )

    lines.extend(["", "## Per Eval", ""])
    for eval_item in report["per_eval"]:
        lines.append(f"### Eval {eval_item['eval_id']}: {eval_item['eval_name']}")
        lines.append(f"- Flags: {', '.join(eval_item['flags']) if eval_item['flags'] else 'none'}")
        for configuration, summary in eval_item["configurations"].items():
            unstable = [key for key, item in summary["expectation_variance"].items() if item["unstable"]]
            lines.append(
                f"- {configuration}: pass mean {summary['pass_rate']['mean']:.4f}, "
                f"stddev {summary['pass_rate']['stddev']:.4f}, "
                f"drift={summary['drift']['drift_detected']}, unstable_expectations={unstable or 'none'}"
            )
        if eval_item["pairwise_results"]:
            pair = eval_item["pairwise_results"][0]
            lines.append(
                f"- pairwise: winner={pair.get('final_winner')} margin={float(pair.get('avg_margin', 0.0) or 0.0):.4f} "
                f"disagreement={pair.get('judge_disagreement', False)}"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_stability_artifacts(iteration_dir: Path, report: dict[str, Any]) -> None:
    iteration_path = Path(iteration_dir)
    write_json(iteration_path / "stability.json", report)
    write_json(iteration_path / "variance-by-expectation.json", report["variance_by_expectation"])
    write_text(iteration_path / "stability.md", _generate_markdown(report))
