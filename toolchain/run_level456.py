from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from toolchain.common import load_json
from toolchain.deep_evals.run_deep_eval import Sender, run_deep_eval
from toolchain.hard_gates.artifact_gate import run_hard_gate
from toolchain.kimi_runtime import CommandRunner
from toolchain.package_snapshot import snapshot_package_state
from toolchain.quantitative.run_quantitative_bundle import (
    build_quantitative_summary,
    write_quantitative_summary_artifacts,
)
from toolchain.quantitative.skill_structure_score import score_skill_structure
from toolchain.benchmarks.stability import generate_stability_report, write_stability_artifacts
from toolchain.reviews.cognitive_review import (
    build_human_review_packet,
    generate_release_recommendation,
    write_human_review_authorization_template,
)


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json(path)
    return data if isinstance(data, dict) else {}


def _supporting_level3_summary(iteration_dir: Path) -> dict[str, Any]:
    existing = _load_optional_json(iteration_dir / "level3-summary.json")
    if existing:
        return existing
    benchmark = _load_optional_json(iteration_dir / "benchmark.json")
    return {
        "metadata": {
            "iteration_dir": str(iteration_dir),
            "skill_name": benchmark.get("metadata", {}).get("skill_name", ""),
            "skill_path": benchmark.get("metadata", {}).get("skill_path", ""),
        },
        "primary_mode": "supporting-not-available",
        "pairwise_summary": {},
        "gate_summary": benchmark.get("run_summary", {}),
        "per_eval": [],
    }


def _ensure_quantitative_summary(iteration_dir: Path, package_dir: Path) -> dict[str, Any]:
    existing = _load_optional_json(iteration_dir / "quantitative-summary.json")
    if existing:
        return existing
    level3_summary = _supporting_level3_summary(iteration_dir)
    stability = generate_stability_report(iteration_dir)
    write_stability_artifacts(iteration_dir, stability)
    structural_diagnostics = score_skill_structure(package_dir)
    summary = build_quantitative_summary(
        iteration_dir,
        level3_summary=level3_summary,
        stability=stability,
        structural_diagnostics=structural_diagnostics,
    )
    write_quantitative_summary_artifacts(iteration_dir, summary)
    return summary


def run_level456(
    iteration_dir: str | Path,
    package_dir: str | Path,
    *,
    sender: Sender | None = None,
    command_runner: CommandRunner | None = None,
    analyzer_model: str | None = None,
    timeout_seconds: int | None = None,
    refresh_review_template: bool = False,
) -> dict[str, Any]:
    """Run the post-execution quality flow on an existing iteration.

    This entry point is kept for compatibility with older "Level 4-6" usage,
    but it now follows the refactored flow:
    hard gate -> quantitative supporting bundle -> deep quality eval -> review.
    """

    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    package_snapshot = snapshot_package_state(package_path, iteration_path)

    hard_gate = run_hard_gate(iteration_path)
    quantitative = _ensure_quantitative_summary(iteration_path, package_path)
    deep_eval_result = run_deep_eval(
        iteration_path,
        package_path,
        sender=sender,
        command_runner=command_runner,
        deep_eval_model=analyzer_model,
        timeout_seconds=timeout_seconds,
    )

    packet = build_human_review_packet(
        iteration_path,
        package_path,
        sender=sender,
        command_runner=command_runner,
        review_model=analyzer_model,
        timeout_seconds=timeout_seconds,
    )
    review_path = iteration_path / "human-review-authorization.json"
    legacy_review_path = iteration_path / "human-review-score.json"
    review_template_written = False
    if refresh_review_template or (not review_path.exists() and not legacy_review_path.exists()):
        write_human_review_authorization_template(iteration_path, package_name=package_path.name)
        review_template_written = True

    recommendation = generate_release_recommendation(iteration_path)
    deep_eval = deep_eval_result["deep_eval"]
    level3_summary = _supporting_level3_summary(iteration_path)

    return {
        "iteration_dir": str(iteration_path),
        "package_dir": str(package_path),
        "quality_primary_mode": deep_eval["metadata"]["quality_primary_mode"],
        "deep_eval_model": deep_eval["metadata"]["deep_eval_model"],
        "analysis_model": deep_eval["metadata"]["deep_eval_model"],
        "hard_gate_passed": hard_gate["passed"],
        "supporting_level3_mode": level3_summary.get("primary_mode", "supporting-not-available"),
        "quantitative_role": quantitative.get("metadata", {}).get("role", "supporting-evidence"),
        "deep_eval_decision": deep_eval.get("release_signal", {}).get("decision", "revise"),
        "representative_runs": packet["representative_runs"],
        "review_template_written": review_template_written,
        "review_authorization_template_written": review_template_written,
        "recommendation": recommendation["recommendation"],
        "blockers": recommendation["blockers"],
        "artifacts": {
            "hard_gate_json": str(iteration_path / "hard-gate.json"),
            "quantitative_summary_json": str(iteration_path / "quantitative-summary.json"),
            "deep_eval_json": str(iteration_path / "deep-eval.json"),
            "quality_failure_tags_json": str(iteration_path / "quality-failure-tags.json"),
            "agent_review_report_json": str(iteration_path / "agent-review-report.json"),
            "human_review_packet": str(iteration_path / "human-review-packet.md"),
            "human_review_authorization": str(iteration_path / "human-review-authorization.json"),
            "release_recommendation": str(iteration_path / "release-recommendation.json"),
            "supporting_level3_summary": str(iteration_path / "level3-summary.json"),
            "supporting_stability": str(iteration_path / "stability.json"),
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
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Vision Skill post-execution quality pipeline.")
    parser.add_argument("--iteration-dir", required=True, help="Path to the executed iteration directory.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory containing SKILL.md.")
    parser.add_argument("--analyzer-model", default=None, help="Optional deep eval model override.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional analyzer timeout override.")
    parser.add_argument(
        "--refresh-review-template",
        action="store_true",
        help="Overwrite any existing human-review-authorization.json template before generating the release recommendation.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_level456(
        args.iteration_dir,
        args.package_dir,
        analyzer_model=args.analyzer_model,
        timeout_seconds=args.timeout_seconds,
        refresh_review_template=args.refresh_review_template,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
