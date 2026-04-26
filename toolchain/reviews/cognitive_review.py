from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.common import load_json, write_json, write_text


RUBRIC_DIMENSIONS = [
    "Protocol Fidelity",
    "Structural Output",
    "Thinking Support",
    "Judgment Preservation",
    "Boundary Safety",
    "VisionTree Voice",
]


def _index_benchmark_runs(benchmark: dict[str, Any]) -> dict[tuple[int, int, str], dict[str, Any]]:
    return {
        (int(run["eval_id"]), int(run["run_number"]), str(run["configuration"])): run
        for run in benchmark.get("runs", [])
    }


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json(path)
    return data if isinstance(data, dict) else {}


def _load_eval_metadata(eval_dir: Path) -> dict[str, Any]:
    metadata = _load_optional_json(eval_dir / "eval_metadata.json")
    return {
        "eval_id": metadata.get("eval_id"),
        "eval_name": metadata.get("eval_name", eval_dir.name),
    }


def _run_number(run_dir: Path) -> int:
    try:
        return int(run_dir.name.split("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def _build_raw_run_meta(run_dir: Path, eval_metadata: dict[str, Any]) -> dict[str, Any]:
    grading = _load_optional_json(run_dir / "grading.json")
    return {
        "eval_id": eval_metadata.get("eval_id"),
        "eval_name": eval_metadata.get("eval_name", ""),
        "configuration": run_dir.parent.name,
        "run_number": _run_number(run_dir),
        "run_dir": str(run_dir),
        "pairwise_winner": "not_available",
        "pairwise_margin": 0.0,
        "judge_disagreement": False,
        "result": grading.get("summary", {}),
    }


def _raw_runs_by_configuration(iteration_dir: Path, configuration: str) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        if not eval_dir.is_dir():
            continue
        eval_metadata = _load_eval_metadata(eval_dir)
        config_dir = eval_dir / configuration
        if not config_dir.exists():
            continue
        for run_dir in sorted(config_dir.glob("run-*")):
            if run_dir.is_dir():
                runs.append(_build_raw_run_meta(run_dir, eval_metadata))
    return runs


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


def _select_representative_runs(
    iteration_dir: Path,
    level3_summary: dict[str, Any],
    benchmark: dict[str, Any],
) -> dict[str, Any]:
    pairwise = level3_summary.get("per_eval", [])
    benchmark_index = _index_benchmark_runs(benchmark)
    wins = [pair for pair in pairwise if pair.get("final_winner") == "with_skill"]
    losses = [pair for pair in pairwise if pair.get("final_winner") == "without_skill"]
    comparable = [pair for pair in pairwise if pair.get("final_winner") != "not_comparable"]

    if not pairwise:
        with_skill_runs = _raw_runs_by_configuration(iteration_dir, "with_skill")
        without_skill_runs = _raw_runs_by_configuration(iteration_dir, "without_skill")
        best_with_skill = with_skill_runs[0] if with_skill_runs else {}
        worst_with_skill = with_skill_runs[-1] if with_skill_runs else {}
        baseline = {}
        if best_with_skill:
            baseline = next(
                (run for run in without_skill_runs if run.get("eval_id") == best_with_skill.get("eval_id")),
                without_skill_runs[0] if without_skill_runs else {},
            )
        return {
            "best_with_skill": best_with_skill,
            "worst_with_skill": worst_with_skill,
            "baseline_comparison": baseline,
        }

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


def _suggested_scores_from_deep_eval(deep_eval: dict[str, Any], hard_gate: dict[str, Any]) -> dict[str, int]:
    signal = deep_eval.get("release_signal", {})
    decision = signal.get("decision", "revise")
    winners = [item.get("winner", "tie") for item in deep_eval.get("per_eval", [])]
    failure_tags = {
        tag
        for item in deep_eval.get("per_eval", [])
        for tag in item.get("failure_tags", [])
    }

    base = 3 if decision == "pass" else 2 if decision == "revise" else 1
    protocol = 2 if hard_gate.get("passed", True) else 0
    structural = 3 if winners and all(winner == "with_skill" for winner in winners) else 2 if "with_skill" in winners else 1
    thinking = base
    judgment = 1 if any("checkpoint-fake" in tag or "judgment" in tag for tag in failure_tags) else min(base, 2)
    boundary = 1 if any("boundary" in tag for tag in failure_tags) else 2
    voice = 1 if any("voice" in tag or "generic" in tag for tag in failure_tags) else 2

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
    benchmark = _load_optional_json(iteration_path / "benchmark.json")
    stability = _load_optional_json(iteration_path / "stability.json")
    analysis = _load_optional_json(iteration_path / "analysis.json")
    deep_eval = _load_optional_json(iteration_path / "deep-eval.json")
    hard_gate = _load_optional_json(iteration_path / "hard-gate.json")
    quantitative = _load_optional_json(iteration_path / "quantitative-summary.json")
    level3_summary = _load_optional_json(iteration_path / "level3-summary.json")
    representative_runs = _select_representative_runs(iteration_path, level3_summary, benchmark)
    repair_recommendations = (
        deep_eval.get("repair_recommendations")
        or analysis.get("repair_recommendations", [])
    )
    quality_primary_mode = deep_eval.get("metadata", {}).get("quality_primary_mode", "legacy-analysis")

    packet = {
        "metadata": {
            "package_name": package_path.name,
            "skill_name": level3_summary.get("metadata", {}).get("skill_name", package_path.name),
            "iteration": iteration_path.name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "summary": {
            "quality_primary_mode": quality_primary_mode,
            "level3_primary_mode": level3_summary.get("primary_mode", "supporting-not-available"),
            "pairwise_summary": level3_summary.get("pairwise_summary", {}),
            "stability_flags": stability.get("overall", {}).get("flags", []),
            "hard_gate_passed": hard_gate.get("passed"),
            "deep_eval_release_signal": deep_eval.get("release_signal", {}),
            "deep_eval_summary": deep_eval.get("cross_eval_summary", {}),
            "quantitative_supporting_risks": quantitative.get("supporting_risks", []),
            "analysis_overall_winner": analysis.get("cross_eval_summary", {}).get(
                "overall_winner",
                analysis.get("cross_eval_summary", {}).get("overall_skill_value", "n/a"),
            ),
            "repair_recommendations": repair_recommendations,
        },
        "representative_runs": representative_runs,
        "suggested_scores": (
            _suggested_scores_from_deep_eval(deep_eval, hard_gate)
            if deep_eval
            else _suggested_scores(level3_summary, stability, analysis)
        ),
        "review_checklist_path": str(Path(__file__).resolve().parents[2] / "shared" / "review-templates" / "human-review-checklist.md"),
        "notes_for_reviewer": [
            "Review whether the representative runs reflect the package's actual behavior.",
            "Use deep-eval as the primary quality evidence; quantitative artifacts are supporting diagnostics.",
            "Use suggested scores only as a starting point.",
            "Final decision must be made by a human reviewer.",
        ],
        "evidence_paths": {
            "hard_gate": str(iteration_path / "hard-gate.json"),
            "deep_eval": str(iteration_path / "deep-eval.json"),
            "quantitative_summary": str(iteration_path / "quantitative-summary.json"),
            "level3_summary": str(iteration_path / "level3-summary.json"),
            "benchmark": str(iteration_path / "benchmark.json"),
            "stability": str(iteration_path / "stability.json"),
            "analysis": str(iteration_path / "analysis.json"),
        },
    }
    write_text(iteration_path / "human-review-packet.md", _packet_markdown(packet))
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
        f"- Quality mode: {packet['summary']['quality_primary_mode']}",
        f"- Level 3 mode: {packet['summary']['level3_primary_mode']}",
        f"- Pairwise summary: {packet['summary']['pairwise_summary']}",
        f"- Hard Gate Passed: {packet['summary']['hard_gate_passed']}",
        f"- Deep Eval Signal: {packet['summary']['deep_eval_release_signal'] or 'n/a'}",
        f"- Quantitative Supporting Risks: {packet['summary']['quantitative_supporting_risks'] or 'none'}",
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
    write_json(iteration_path / "human-review-score.json", template)
    return template


def generate_release_recommendation(iteration_dir: Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    level3_summary = _load_optional_json(iteration_path / "level3-summary.json")
    stability = _load_optional_json(iteration_path / "stability.json")
    analysis = _load_optional_json(iteration_path / "analysis.json")
    hard_gate = _load_optional_json(iteration_path / "hard-gate.json")
    quantitative = _load_optional_json(iteration_path / "quantitative-summary.json")
    deep_eval = _load_optional_json(iteration_path / "deep-eval.json")
    review_path = iteration_path / "human-review-score.json"
    review = load_json(review_path) if review_path.exists() else None

    blockers: list[str] = []
    if hard_gate and not hard_gate.get("passed", False):
        blockers.append("hard_gate_failed")
        blockers.extend(hard_gate.get("blockers", []))

    if deep_eval:
        deep_decision = deep_eval.get("release_signal", {}).get("decision", "revise")
        if deep_decision in {"revise", "hold"}:
            blockers.append(f"deep_eval_decision:{deep_decision}")
    else:
        blockers.append("deep_eval_missing")

    recommendation = "pending-human-review"
    if review:
        decision = review.get("decision", "hold")
        if decision == "pass":
            if hard_gate and not hard_gate.get("passed", False):
                recommendation = "hold"
                blockers.append("manual_pass_blocked_by_hard_gate")
            elif deep_eval and deep_eval.get("release_signal", {}).get("decision") == "hold":
                recommendation = "hold"
                blockers.append("manual_pass_blocked_by_deep_eval_hold")
            else:
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
            "hard_gate_completed": (iteration_path / "hard-gate.json").exists(),
            "hard_gate_passed": hard_gate.get("passed") if hard_gate else None,
            "deep_eval_completed": (iteration_path / "deep-eval.json").exists(),
            "quantitative_summary_completed": (iteration_path / "quantitative-summary.json").exists(),
            "supporting_level3_completed": (iteration_path / "level3-summary.json").exists(),
            "supporting_benchmark_completed": (iteration_path / "benchmark.json").exists(),
            "supporting_stability_completed": (iteration_path / "stability.json").exists(),
            "legacy_analysis_completed": (iteration_path / "analysis.json").exists(),
            "human_review_completed": review is not None,
        },
        "quality_primary_mode": deep_eval.get("metadata", {}).get("quality_primary_mode", "legacy-analysis") if deep_eval else "legacy-analysis",
        "deep_eval_release_signal": deep_eval.get("release_signal", {}) if deep_eval else {},
        "quantitative_supporting_risks": quantitative.get("supporting_risks", []) if quantitative else [],
        "recommendation": recommendation,
        "blockers": sorted(set(blockers)),
        "notes": deep_eval.get("repair_recommendations", analysis.get("repair_recommendations", [])) if deep_eval else analysis.get("repair_recommendations", []),
    }
    write_json(iteration_path / "release-recommendation.json", result)
    return result
