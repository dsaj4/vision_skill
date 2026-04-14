from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.benchmarks.level3_summary import ensure_level3_summary


RUBRIC_DIMENSIONS = [
    "Protocol Fidelity",
    "Structural Output",
    "Thinking Support",
    "Judgment Preservation",
    "Boundary Safety",
    "VisionTree Voice",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _index_benchmark_runs(benchmark: dict[str, Any]) -> dict[tuple[int, int, str], dict[str, Any]]:
    return {
        (int(run["eval_id"]), int(run["run_number"]), str(run["configuration"])): run
        for run in benchmark.get("runs", [])
    }


def _build_run_meta(pair: dict[str, Any], configuration: str, benchmark_index: dict[tuple[int, int, str], dict[str, Any]]) -> dict[str, Any]:
    run = benchmark_index.get((int(pair["eval_id"]), int(pair["run_number"]), configuration), {})
    run_dir_key = "with_skill_run_dir" if configuration == "with_skill" else "without_skill_run_dir"
    return {
        "eval_id": pair["eval_id"],
        "eval_name": pair["eval_name"],
        "configuration": configuration,
        "run_number": pair["run_number"],
        "run_dir": pair.get(run_dir_key, ""),
        "pairwise_winner": pair.get("final_winner", "not_comparable"),
        "pairwise_margin": float(pair.get("avg_margin", 0.0) or 0.0),
        "judge_disagreement": bool(pair.get("judge_disagreement", False)),
        "result": run.get("result", {}),
    }


def _select_representative_runs(level3_summary: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    pairwise = level3_summary.get("per_eval", [])
    benchmark_index = _index_benchmark_runs(benchmark)
    wins = [pair for pair in pairwise if pair.get("final_winner") == "with_skill"]
    losses = [pair for pair in pairwise if pair.get("final_winner") == "without_skill"]
    comparable = [pair for pair in pairwise if pair.get("final_winner") != "not_comparable"]

    best_pair = max(wins or comparable, key=lambda item: float(item.get("avg_margin", 0.0) or 0.0), default={})
    if losses:
        worst_pair = max(losses, key=lambda item: float(item.get("avg_margin", 0.0) or 0.0), default={})
    else:
        worst_pair = min(comparable, key=lambda item: float(item.get("avg_margin", 0.0) or 0.0), default={})

    baseline_pair = best_pair or (comparable[0] if comparable else {})

    return {
        "best_with_skill": _build_run_meta(best_pair, "with_skill", benchmark_index) if best_pair else {},
        "worst_with_skill": _build_run_meta(worst_pair, "with_skill", benchmark_index) if worst_pair else {},
        "baseline_comparison": _build_run_meta(baseline_pair, "without_skill", benchmark_index) if baseline_pair else {},
    }


def _suggested_scores(level3_summary: dict[str, Any], stability: dict[str, Any], analysis: dict[str, Any]) -> dict[str, int]:
    gate = level3_summary.get("gate_summary", {})
    pairwise = level3_summary.get("pairwise_summary", {})
    with_pass = gate.get("with_skill", {}).get("pass_rate", {}).get("mean", 0.0)
    win_rate = float(pairwise.get("win_rate", 0.0) or 0.0)
    cost_adjusted_value = float(pairwise.get("cost_adjusted_value", 0.0) or 0.0)
    instability_flags = set(stability.get("overall", {}).get("flags", []))
    failure_tags = set()
    for item in analysis.get("per_eval", []):
        failure_tags.update(item.get("failure_tags", []))

    protocol = 3 if with_pass >= 0.95 else 2 if with_pass >= 0.8 else 1 if with_pass >= 0.6 else 0
    structural = 3 if win_rate >= 0.75 else 2 if win_rate >= 0.5 else 1
    thinking = 2 if analysis.get("cross_eval_summary", {}).get("overall_winner") == "with_skill" and cost_adjusted_value > 0 else 1
    judgment = 2 if "template.checkpoint-fake" not in failure_tags else 1
    boundary = 1 if "skill-content.boundary-weak" in failure_tags else 2
    voice = 1 if "template.voice-drift" in failure_tags else 2

    if "unstable" in instability_flags or "weak_stability_value" in instability_flags or "instability_risk" in instability_flags:
        protocol = max(protocol - 1, 0)
        thinking = max(thinking - 1, 0)

    return {
        "Protocol Fidelity": protocol,
        "Structural Output": structural,
        "Thinking Support": thinking,
        "Judgment Preservation": judgment,
        "Boundary Safety": boundary,
        "VisionTree Voice": voice,
    }


def build_human_review_packet(iteration_dir: Path, package_dir: Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    benchmark = _load_json(iteration_path / "benchmark.json")
    stability = _load_json(iteration_path / "stability.json")
    analysis = _load_json(iteration_path / "analysis.json")
    level3_summary = ensure_level3_summary(iteration_path)
    representative_runs = _select_representative_runs(level3_summary, benchmark)

    packet = {
        "metadata": {
            "package_name": package_path.name,
            "skill_name": level3_summary.get("metadata", {}).get("skill_name", package_path.name),
            "iteration": iteration_path.name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "summary": {
            "level3_primary_mode": level3_summary.get("primary_mode", "unknown"),
            "pairwise_summary": level3_summary.get("pairwise_summary", {}),
            "stability_flags": stability.get("overall", {}).get("flags", []),
            "analysis_overall_winner": analysis.get("cross_eval_summary", {}).get(
                "overall_winner",
                analysis.get("cross_eval_summary", {}).get("overall_skill_value", "n/a"),
            ),
            "repair_recommendations": analysis.get("repair_recommendations", []),
        },
        "representative_runs": representative_runs,
        "suggested_scores": _suggested_scores(level3_summary, stability, analysis),
        "review_checklist_path": str(Path(__file__).resolve().parents[2] / "shared" / "review-templates" / "human-review-checklist.md"),
        "notes_for_reviewer": [
            "Review whether the representative runs reflect the package's actual behavior.",
            "Use suggested scores only as a starting point.",
            "Final decision must be made by a human reviewer.",
        ],
        "evidence_paths": {
            "level3_summary": str(iteration_path / "level3-summary.json"),
            "benchmark": str(iteration_path / "benchmark.json"),
            "stability": str(iteration_path / "stability.json"),
            "analysis": str(iteration_path / "analysis.json"),
        },
    }
    (iteration_path / "human-review-packet.md").write_text(_packet_markdown(packet), encoding="utf-8")
    return packet


def _packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Human Review Packet",
        "",
        f"**Package**: {packet['metadata']['package_name']}",
        f"**Iteration**: {packet['metadata']['iteration']}",
        "",
        "## Summary",
        "",
        f"- Level 3 mode: {packet['summary']['level3_primary_mode']}",
        f"- Pairwise summary: {packet['summary']['pairwise_summary']}",
        f"- Stability Flags: {packet['summary']['stability_flags'] or 'none'}",
        f"- Analysis Overall Winner: {packet['summary']['analysis_overall_winner']}",
        f"- Repair Recommendations: {packet['summary']['repair_recommendations']}",
        "",
        "## Suggested Scores",
        "",
    ]
    for key, value in packet["suggested_scores"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Representative Runs", ""])
    for key, run_meta in packet["representative_runs"].items():
        if run_meta:
            lines.append(
                f"- {key}: eval {run_meta['eval_id']} / {run_meta['configuration']} / run-{run_meta['run_number']} / "
                f"pairwise={run_meta['pairwise_winner']} / pass_rate {run_meta.get('result', {}).get('pass_rate', 'n/a')}"
            )
    lines.extend(["", "## Evidence Paths", ""])
    for key, value in packet["evidence_paths"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"


def write_human_review_template(iteration_dir: Path, package_name: str) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    template = {
        "reviewer": "",
        "reviewed_at": "",
        "package_name": package_name,
        "iteration": iteration_path.name,
        "scores": {dimension: None for dimension in RUBRIC_DIMENSIONS},
        "decision": "hold",
        "notes": "",
    }
    _write_json(iteration_path / "human-review-score.json", template)
    return template


def generate_release_recommendation(iteration_dir: Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    level3_summary = ensure_level3_summary(iteration_path)
    stability = _load_json(iteration_path / "stability.json")
    analysis = _load_json(iteration_path / "analysis.json")
    review_path = iteration_path / "human-review-score.json"
    review = _load_json(review_path) if review_path.exists() else None

    blockers: list[str] = []
    if stability.get("overall", {}).get("flags"):
        blockers.extend(stability["overall"]["flags"])
    if not analysis.get("per_eval"):
        blockers.append("analysis_missing")
    if float(level3_summary.get("pairwise_summary", {}).get("win_rate", 0.0) or 0.0) <= 0.5:
        blockers.append("level3_value_not_positive")
    if float(level3_summary.get("pairwise_summary", {}).get("cost_adjusted_value", 0.0) or 0.0) <= 0.0:
        blockers.append("level3_cost_adjusted_value_non_positive")

    recommendation = "pending-human-review"
    if review:
        decision = review.get("decision", "hold")
        if decision == "pass":
            recommendation = "promote"
        elif decision == "revise":
            recommendation = "revise"
            blockers.append("manual_review_decision:revise")
        else:
            recommendation = "hold"
            blockers.append("manual_review_decision:hold")
    else:
        blockers.append("human_review_pending")

    result = {
        "metadata": {
            "iteration": iteration_path.name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill_name": level3_summary.get("metadata", {}).get("skill_name", ""),
        },
        "minimum_gates": {
            "level3_completed": (iteration_path / "level3-summary.json").exists(),
            "benchmark_completed": (iteration_path / "benchmark.json").exists(),
            "stability_completed": (iteration_path / "stability.json").exists(),
            "analysis_completed": (iteration_path / "analysis.json").exists(),
            "human_review_completed": review is not None,
        },
        "recommendation": recommendation,
        "blockers": sorted(set(blockers)),
        "notes": analysis.get("repair_recommendations", []),
    }
    _write_json(iteration_path / "release-recommendation.json", result)
    return result
