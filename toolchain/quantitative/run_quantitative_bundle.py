from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from toolchain.benchmarks.level3_summary import generate_level3_summary, write_level3_summary_artifacts
from toolchain.benchmarks.run_benchmark import grade_iteration_runs
from toolchain.benchmarks.run_differential_benchmark import run_differential_benchmark
from toolchain.benchmarks.stability import generate_stability_report, write_stability_artifacts
from toolchain.common import load_json, write_json, write_text
from toolchain.judges.pairwise_judge import Sender as JudgeSender
from toolchain.kimi_runtime import CommandRunner
from toolchain.quantitative.skill_structure_score import score_skill_structure


def _package_skill_name(package_dir: Path) -> str:
    metadata_path = package_dir / "metadata" / "package.json"
    if not metadata_path.exists():
        return package_dir.name
    metadata = load_json(metadata_path)
    return str(metadata.get("skill_name") or metadata.get("package_name") or package_dir.name)


def _supporting_risks(level3_summary: dict[str, Any], stability: dict[str, Any]) -> list[str]:
    risks = list(stability.get("overall", {}).get("flags", []))
    pairwise = level3_summary.get("pairwise_summary", {})
    if float(pairwise.get("win_rate", 0.0) or 0.0) <= 0.5:
        risks.append("quantitative_win_rate_not_positive")
    if float(pairwise.get("cost_adjusted_value", 0.0) or 0.0) <= 0.0:
        risks.append("quantitative_cost_adjusted_value_non_positive")
    if float(pairwise.get("judge_disagreement_rate", 0.0) or 0.0) >= 0.25:
        risks.append("quantitative_judge_disagreement_high")
    return sorted(set(risks))


def _merge_supporting_risks(
    level3_summary: dict[str, Any],
    stability: dict[str, Any],
    structural_diagnostics: dict[str, Any],
) -> list[str]:
    risks = _supporting_risks(level3_summary, stability)
    risks.extend(str(item) for item in structural_diagnostics.get("risks", []))
    return sorted(set(risks))


def build_quantitative_summary(
    iteration_dir: str | Path,
    *,
    level3_summary: dict[str, Any],
    stability: dict[str, Any],
    structural_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    return {
        "metadata": {
            "iteration_dir": str(iteration_path),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "role": "supporting-evidence",
        },
        "primary_quality_policy": {
            "quality_decision_source": "deep-eval.json",
            "quantitative_role": "supporting diagnostics only",
        },
        "artifacts": {
            "benchmark": str(iteration_path / "benchmark.json"),
            "differential_benchmark": str(iteration_path / "differential-benchmark.json"),
            "level3_summary": str(iteration_path / "level3-summary.json"),
            "stability": str(iteration_path / "stability.json"),
            "variance_by_expectation": str(iteration_path / "variance-by-expectation.json"),
        },
        "gate_summary": level3_summary.get("gate_summary", {}),
        "pairwise_summary": level3_summary.get("pairwise_summary", {}),
        "judge_strategy": level3_summary.get("metadata", {}).get("judge_strategy", "unknown"),
        "stability_summary": stability.get("overall", {}),
        "structural_diagnostics": structural_diagnostics,
        "weighted_structure_score": structural_diagnostics.get("weighted_structure_score", {}),
        "supporting_risks": _merge_supporting_risks(level3_summary, stability, structural_diagnostics),
    }


def _markdown(summary: dict[str, Any]) -> str:
    pairwise = summary.get("pairwise_summary", {})
    stability = summary.get("stability_summary", {})
    structure_score = summary.get("weighted_structure_score", {})
    lines = [
        "# Quantitative Summary",
        "",
        f"**Generated At**: {summary['metadata']['generated_at']}",
        "",
        "This bundle is supporting evidence. Deep quality evaluation is the main quality judgment.",
        "",
        "## Pairwise",
        "",
        f"- Judge strategy: {summary.get('judge_strategy', 'unknown')}",
        f"- Win rate: {float(pairwise.get('win_rate', 0.0) or 0.0):.4f}",
        f"- Tie rate: {float(pairwise.get('tie_rate', 0.0) or 0.0):.4f}",
        f"- Avg margin: {float(pairwise.get('avg_margin', 0.0) or 0.0):.4f}",
        f"- Cost-adjusted value: {float(pairwise.get('cost_adjusted_value', 0.0) or 0.0):.4f}",
        f"- Judge disagreement rate: {float(pairwise.get('judge_disagreement_rate', 0.0) or 0.0):.4f}",
        "",
        "## Stability",
        "",
        f"- Flags: {', '.join(stability.get('flags', [])) if stability.get('flags') else 'none'}",
        "",
        "## Structural Diagnostics",
        "",
        f"- Score: {structure_score.get('score', 0)} / {structure_score.get('max_score', 60)}",
        f"- Role: {structure_score.get('role', 'diagnostic-only')}",
        "",
        "## Supporting Risks",
        "",
    ]
    risks = summary.get("supporting_risks", [])
    if not risks:
        lines.append("- none")
    else:
        for risk in risks:
            lines.append(f"- {risk}")
    return "\n".join(lines).strip() + "\n"


def write_quantitative_summary_artifacts(iteration_dir: str | Path, summary: dict[str, Any]) -> dict[str, str]:
    iteration_path = Path(iteration_dir)
    json_path = iteration_path / "quantitative-summary.json"
    markdown_path = iteration_path / "quantitative-summary.md"
    write_json(json_path, summary)
    write_text(markdown_path, _markdown(summary))
    return {
        "quantitative_summary_json": str(json_path),
        "quantitative_summary_markdown": str(markdown_path),
    }


def run_quantitative_bundle(
    iteration_dir: str | Path,
    package_dir: str | Path,
    *,
    skill_name: str | None = None,
    sender: JudgeSender | None = None,
    command_runner: CommandRunner | None = None,
    judge_model: str | None = None,
    timeout_seconds: int | None = None,
    balanced_judging: bool = False,
) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    resolved_skill_name = skill_name or _package_skill_name(package_path)

    benchmark_result = grade_iteration_runs(
        iteration_path,
        skill_name=resolved_skill_name,
        skill_path=str(package_path),
    )
    differential_result = run_differential_benchmark(
        iteration_path,
        skill_name=resolved_skill_name,
        skill_path=str(package_path),
        sender=sender,
        command_runner=command_runner,
        judge_model=judge_model,
        timeout_seconds=timeout_seconds,
        judge_strategy="balanced" if balanced_judging else "single",
    )
    level3_summary = generate_level3_summary(iteration_path)
    level3_paths = write_level3_summary_artifacts(iteration_path, level3_summary)
    stability = generate_stability_report(iteration_path)
    write_stability_artifacts(iteration_path, stability)
    structural_diagnostics = score_skill_structure(package_path)
    quantitative_summary = build_quantitative_summary(
        iteration_path,
        level3_summary=level3_summary,
        stability=stability,
        structural_diagnostics=structural_diagnostics,
    )
    quantitative_paths = write_quantitative_summary_artifacts(iteration_path, quantitative_summary)

    return {
        "iteration_dir": str(iteration_path),
        "package_dir": str(package_path),
        "benchmark": benchmark_result,
        "differential": differential_result,
        "level3_summary": level3_summary,
        "stability": stability,
        "quantitative_summary": quantitative_summary,
        "artifacts": {
            "benchmark_json": benchmark_result["benchmark_path"],
            "benchmark_markdown": benchmark_result["benchmark_markdown_path"],
            "differential_benchmark_json": str(iteration_path / "differential-benchmark.json"),
            "differential_benchmark_markdown": str(iteration_path / "differential-benchmark.md"),
            "level3_summary_json": level3_paths["level3_summary_json"],
            "level3_summary_markdown": level3_paths["level3_summary_markdown"],
            "stability_json": str(iteration_path / "stability.json"),
            "stability_markdown": str(iteration_path / "stability.md"),
            "variance_by_expectation_json": str(iteration_path / "variance-by-expectation.json"),
            **quantitative_paths,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run supporting quantitative artifacts for an iteration.")
    parser.add_argument("--iteration-dir", required=True, help="Path to the iteration directory.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory.")
    parser.add_argument("--skill-name", default=None, help="Optional skill name override.")
    parser.add_argument("--judge-model", default=None, help="Optional judge model override.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional timeout override.")
    parser.add_argument("--balanced-judging", action="store_true", help="Use slower forward + reversed pairwise judging. Default is single-pass.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_quantitative_bundle(
        args.iteration_dir,
        args.package_dir,
        skill_name=args.skill_name,
        judge_model=args.judge_model,
        timeout_seconds=args.timeout_seconds,
        balanced_judging=args.balanced_judging,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
