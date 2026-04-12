from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def _select_representative_runs(benchmark: dict[str, Any]) -> dict[str, Any]:
    runs = benchmark.get("runs", [])
    with_skill_runs = [run for run in runs if run.get("configuration") == "with_skill"]
    without_skill_runs = [run for run in runs if run.get("configuration") == "without_skill"]

    best_with_skill = max(
        with_skill_runs,
        key=lambda run: (run["result"].get("pass_rate", 0.0), -run["result"].get("time_seconds", 0.0), -run["result"].get("tokens", 0)),
        default={},
    )
    worst_with_skill = min(
        with_skill_runs,
        key=lambda run: (run["result"].get("pass_rate", 0.0), run["result"].get("time_seconds", 0.0), run["result"].get("tokens", 0)),
        default={},
    )

    baseline_comparison = {}
    if best_with_skill:
        matched = [
            run
            for run in without_skill_runs
            if run.get("eval_id") == best_with_skill.get("eval_id")
            and run.get("run_number") == best_with_skill.get("run_number")
        ]
        if matched:
            baseline_comparison = matched[0]
        else:
            same_eval = [run for run in without_skill_runs if run.get("eval_id") == best_with_skill.get("eval_id")]
            if same_eval:
                baseline_comparison = max(same_eval, key=lambda run: run["result"].get("pass_rate", 0.0))
    if not baseline_comparison and without_skill_runs:
        baseline_comparison = max(without_skill_runs, key=lambda run: run["result"].get("pass_rate", 0.0))

    return {
        "best_with_skill": best_with_skill,
        "worst_with_skill": worst_with_skill,
        "baseline_comparison": baseline_comparison,
    }


def _suggested_scores(benchmark: dict[str, Any], stability: dict[str, Any], analysis: dict[str, Any]) -> dict[str, int]:
    with_pass = benchmark.get("run_summary", {}).get("with_skill", {}).get("pass_rate", {}).get("mean", 0.0)
    without_pass = benchmark.get("run_summary", {}).get("without_skill", {}).get("pass_rate", {}).get("mean", 0.0)
    instability_flags = set(stability.get("overall", {}).get("flags", []))
    failure_tags = set()
    for item in analysis.get("per_eval", []):
        failure_tags.update(item.get("failure_tags", []))

    protocol = 3 if with_pass >= 0.95 else 2 if with_pass >= 0.8 else 1 if with_pass >= 0.6 else 0
    structural = 3 if with_pass > without_pass else 2 if with_pass >= 0.8 else 1
    thinking = 2 if analysis.get("cross_eval_summary", {}).get("overall_winner") == "with_skill" else 1
    judgment = 2 if "template.checkpoint-fake" not in failure_tags else 1
    boundary = 1 if "skill-content.boundary-weak" in failure_tags else 2
    voice = 1 if "template.voice-drift" in failure_tags else 2

    if "unstable" in instability_flags or "weak_stability_value" in instability_flags:
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


def _find_run_dir(iteration_dir: Path, run_meta: dict[str, Any]) -> Path | None:
    if not run_meta:
        return None
    run_dir = (
        iteration_dir
        / f"eval-{run_meta['eval_id']}-{run_meta['eval_name']}"
        / run_meta["configuration"]
        / f"run-{run_meta['run_number']}"
    )
    return run_dir if run_dir.exists() else None


def build_human_review_packet(iteration_dir: Path, package_dir: Path) -> dict[str, Any]:
    iteration_dir = Path(iteration_dir)
    package_dir = Path(package_dir)
    benchmark = _load_json(iteration_dir / "benchmark.json")
    stability = _load_json(iteration_dir / "stability.json")
    analysis = _load_json(iteration_dir / "analysis.json")
    representative_runs = _select_representative_runs(benchmark)

    packet = {
        "metadata": {
            "package_name": package_dir.name,
            "skill_name": benchmark.get("metadata", {}).get("skill_name", package_dir.name),
            "iteration": iteration_dir.name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "summary": {
            "benchmark_flags": benchmark.get("notes", []),
            "stability_flags": stability.get("overall", {}).get("flags", []),
            "analysis_overall_winner": analysis.get("cross_eval_summary", {}).get(
                "overall_winner",
                analysis.get("cross_eval_summary", {}).get("overall_skill_value", "n/a"),
            ),
            "repair_recommendations": analysis.get("repair_recommendations", []),
        },
        "representative_runs": representative_runs,
        "suggested_scores": _suggested_scores(benchmark, stability, analysis),
        "review_checklist_path": str(Path(__file__).resolve().parents[2] / "shared" / "review-templates" / "human-review-checklist.md"),
        "notes_for_reviewer": [
            "Review whether the representative runs reflect the package's actual behavior.",
            "Use suggested scores only as a starting point.",
            "Final decision must be made by a human reviewer.",
        ],
    }

    best_dir = _find_run_dir(iteration_dir, representative_runs.get("best_with_skill", {}))
    worst_dir = _find_run_dir(iteration_dir, representative_runs.get("worst_with_skill", {}))
    baseline_dir = _find_run_dir(iteration_dir, representative_runs.get("baseline_comparison", {}))

    packet["evidence_paths"] = {
        "best_with_skill": str(best_dir) if best_dir else "",
        "worst_with_skill": str(worst_dir) if worst_dir else "",
        "baseline_comparison": str(baseline_dir) if baseline_dir else "",
        "benchmark": str(iteration_dir / "benchmark.json"),
        "stability": str(iteration_dir / "stability.json"),
        "analysis": str(iteration_dir / "analysis.json"),
    }
    (iteration_dir / "human-review-packet.md").write_text(_packet_markdown(packet), encoding="utf-8")
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
                f"- {key}: eval {run_meta['eval_id']} / {run_meta['configuration']} / run-{run_meta['run_number']} / pass_rate {run_meta['result']['pass_rate']}"
            )
    lines.extend(["", "## Evidence Paths", ""])
    for key, value in packet["evidence_paths"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines).strip() + "\n"


def write_human_review_template(iteration_dir: Path, package_name: str) -> dict[str, Any]:
    iteration_dir = Path(iteration_dir)
    template = {
        "reviewer": "",
        "reviewed_at": "",
        "package_name": package_name,
        "iteration": iteration_dir.name,
        "scores": {dimension: None for dimension in RUBRIC_DIMENSIONS},
        "decision": "hold",
        "notes": "",
    }
    _write_json(iteration_dir / "human-review-score.json", template)
    return template


def generate_release_recommendation(iteration_dir: Path) -> dict[str, Any]:
    iteration_dir = Path(iteration_dir)
    benchmark = _load_json(iteration_dir / "benchmark.json")
    stability = _load_json(iteration_dir / "stability.json")
    analysis = _load_json(iteration_dir / "analysis.json")
    review_path = iteration_dir / "human-review-score.json"
    review = _load_json(review_path) if review_path.exists() else None

    blockers: list[str] = []
    if stability.get("overall", {}).get("flags"):
        blockers.extend(stability["overall"]["flags"])
    if not analysis.get("per_eval"):
        blockers.append("analysis_missing")

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
            "iteration": iteration_dir.name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "skill_name": benchmark.get("metadata", {}).get("skill_name", ""),
        },
        "minimum_gates": {
            "benchmark_completed": (iteration_dir / "benchmark.json").exists(),
            "stability_completed": (iteration_dir / "stability.json").exists(),
            "analysis_completed": (iteration_dir / "analysis.json").exists(),
            "human_review_completed": review is not None,
        },
        "recommendation": recommendation,
        "blockers": sorted(set(blockers)),
        "notes": analysis.get("repair_recommendations", []),
    }
    _write_json(iteration_dir / "release-recommendation.json", result)
    return result
