from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PAUSE_MARKERS = ['回复"继续"', '回复"不对"', '回复"直接要结果"', "输出后暂停", "暂停确认"]
SWOT_GROUPS = [
    ("strengths", "优势"),
    ("weaknesses", "劣势"),
    ("opportunities", "机会"),
    ("threats", "威胁"),
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
        eval_metadata = _load_json(eval_dir / "eval_metadata.json")
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
                grading_path = run_dir / "grading.json"
                if not grading_path.exists():
                    continue
                grading = _load_json(grading_path)
                timing_path = run_dir / "timing.json"
                timing = _load_json(timing_path) if timing_path.exists() else grading.get("timing", {})
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


def _overall_from_per_eval(per_eval: list[dict[str, Any]]) -> dict[str, Any]:
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

    with_skill = configurations_summary.get("with_skill", {})
    without_skill = configurations_summary.get("without_skill", {})
    with_pass = with_skill.get("pass_rate", {}).get("mean", 0.0)
    without_pass = without_skill.get("pass_rate", {}).get("mean", 0.0)
    with_time = with_skill.get("time_seconds", {}).get("mean", 0.0)
    without_time = without_skill.get("time_seconds", {}).get("mean", 0.0)
    with_tokens = with_skill.get("tokens", {}).get("mean", 0.0)
    without_tokens = without_skill.get("tokens", {}).get("mean", 0.0)

    if with_pass <= without_pass and (with_time > without_time or with_tokens > without_tokens):
        flags.append("weak_stability_value")

    with_std = with_skill.get("pass_rate", {}).get("stddev", 0.0)
    without_std = without_skill.get("pass_rate", {}).get("stddev", 0.0)
    if with_std - without_std >= 0.15:
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
    iteration_dir = Path(iteration_dir)
    loaded = _load_iteration_runs(iteration_dir)
    per_eval: list[dict[str, Any]] = []
    runs_per_configuration = 0

    for eval_item in loaded["evals"]:
        config_summaries: dict[str, Any] = {}
        flags: list[str] = []
        for configuration, runs in eval_item["configurations"].items():
            runs_per_configuration = max(runs_per_configuration, len(runs))
            summary = _summarize_configuration(runs)
            config_summaries[configuration] = summary
            if any(item["unstable"] for item in summary["expectation_variance"].values()):
                flags.append("unstable")
            if summary["drift"]["drift_detected"]:
                flags.append("drift_detected")

        with_skill_summary = config_summaries.get("with_skill")
        without_skill_summary = config_summaries.get("without_skill")
        if with_skill_summary and without_skill_summary:
            if with_skill_summary["pass_rate"]["stddev"] - without_skill_summary["pass_rate"]["stddev"] >= 0.15:
                flags.append("instability_risk")

        per_eval.append(
            {
                "eval_id": eval_item["eval_id"],
                "eval_name": eval_item["eval_name"],
                "configurations": config_summaries,
                "flags": sorted(set(flags)),
            }
        )

    report = {
        "metadata": {
            "iteration_dir": str(iteration_dir),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "runs_per_configuration": runs_per_configuration,
            "eval_ids": [item["eval_id"] for item in per_eval],
        },
        "per_eval": per_eval,
        "overall": _overall_from_per_eval(per_eval),
        "variance_by_expectation": _variance_by_expectation(per_eval),
    }
    return report


def _generate_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Stability Report",
        "",
        f"**Generated At**: {report['metadata']['generated_at']}",
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
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_stability_artifacts(iteration_dir: Path, report: dict[str, Any]) -> None:
    iteration_dir = Path(iteration_dir)
    _write_json(iteration_dir / "stability.json", report)
    _write_json(iteration_dir / "variance-by-expectation.json", report["variance_by_expectation"])
    (iteration_dir / "stability.md").write_text(_generate_markdown(report), encoding="utf-8")
