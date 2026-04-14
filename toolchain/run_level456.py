from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from toolchain.analyzers.mechanism_analyzer import Sender, analyze_iteration
from toolchain.benchmarks.level3_summary import ensure_level3_summary
from toolchain.benchmarks.stability import generate_stability_report, write_stability_artifacts
from toolchain.reviews.cognitive_review import (
    build_human_review_packet,
    generate_release_recommendation,
    write_human_review_template,
)


def run_level456(
    iteration_dir: str | Path,
    package_dir: str | Path,
    *,
    sender: Sender | None = None,
    api_key: str | None = None,
    analyzer_model: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: int | None = None,
    refresh_review_template: bool = False,
) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    level3_summary = ensure_level3_summary(iteration_path)

    stability = generate_stability_report(iteration_path)
    write_stability_artifacts(iteration_path, stability)

    analysis_result = analyze_iteration(
        iteration_path,
        package_path,
        sender=sender,
        api_key=api_key,
        analyzer_model=analyzer_model,
        endpoint=endpoint,
        timeout_seconds=timeout_seconds,
    )

    packet = build_human_review_packet(iteration_path, package_path)
    review_path = iteration_path / "human-review-score.json"
    review_template_written = False
    if refresh_review_template or not review_path.exists():
        write_human_review_template(iteration_path, package_name=package_path.name)
        review_template_written = True

    recommendation = generate_release_recommendation(iteration_path)
    analysis = analysis_result["analysis"]

    return {
        "iteration_dir": str(iteration_path),
        "package_dir": str(package_path),
        "level3_primary_mode": level3_summary.get("primary_mode", "unknown"),
        "level3_summary_path": str(iteration_path / "level3-summary.json"),
        "analysis_model": analysis["metadata"]["analyzer_model"],
        "stability_flags": stability["overall"]["flags"],
        "representative_runs": packet["representative_runs"],
        "review_template_written": review_template_written,
        "recommendation": recommendation["recommendation"],
        "blockers": recommendation["blockers"],
        "artifacts": {
            "level3_summary_json": str(iteration_path / "level3-summary.json"),
            "stability_json": str(iteration_path / "stability.json"),
            "analysis_json": str(iteration_path / "analysis.json"),
            "human_review_packet": str(iteration_path / "human-review-packet.md"),
            "human_review_score": str(iteration_path / "human-review-score.json"),
            "release_recommendation": str(iteration_path / "release-recommendation.json"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Vision Skill Level 4-6 post-benchmark pipeline.")
    parser.add_argument("--iteration-dir", required=True, help="Path to the prepared and benchmarked iteration directory.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory containing SKILL.md.")
    parser.add_argument("--api-key", default=None, help="Optional DashScope API key override for analyzer calls.")
    parser.add_argument("--analyzer-model", default=None, help="Optional analyzer model override.")
    parser.add_argument("--endpoint", default=None, help="Optional analyzer endpoint override.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional analyzer timeout override.")
    parser.add_argument(
        "--refresh-review-template",
        action="store_true",
        help="Overwrite any existing human-review-score.json template before generating the release recommendation.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_level456(
        args.iteration_dir,
        args.package_dir,
        api_key=args.api_key,
        analyzer_model=args.analyzer_model,
        endpoint=args.endpoint,
        timeout_seconds=args.timeout_seconds,
        refresh_review_template=args.refresh_review_template,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
