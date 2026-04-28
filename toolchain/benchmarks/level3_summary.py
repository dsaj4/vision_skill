from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.common import load_json, write_json, write_text


def _require_artifact(iteration_dir: Path, name: str) -> Path:
    path = iteration_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Missing required Level 3 artifact: {path}")
    return path


def generate_level3_summary(iteration_dir: str | Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    benchmark = load_json(_require_artifact(iteration_path, "benchmark.json"))
    differential = load_json(_require_artifact(iteration_path, "differential-benchmark.json"))
    consensus = load_json(_require_artifact(iteration_path, "pairwise-consensus.json"))

    pairwise_summary = differential.get("summary", {})
    gate_summary = benchmark.get("run_summary", {})
    pairs = consensus.get("pairs", [])

    return {
        "metadata": {
            "iteration_dir": str(iteration_path),
            "skill_name": differential.get("metadata", {}).get(
                "skill_name",
                benchmark.get("metadata", {}).get("skill_name", "<skill-name>"),
            ),
            "skill_path": differential.get("metadata", {}).get(
                "skill_path",
                benchmark.get("metadata", {}).get("skill_path", "<skill-path>"),
            ),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "eval_ids": sorted({item.get("eval_id") for item in pairs if item.get("eval_id") is not None}),
            "judge_strategy": differential.get("metadata", {}).get("judge_strategy", "unknown"),
        },
        "primary_mode": "differential",
        "primary_artifact_path": str(iteration_path / "differential-benchmark.json"),
        "supporting_gate_artifact_path": str(iteration_path / "benchmark.json"),
        "pairwise_summary": {
            "win_rate": float(pairwise_summary.get("win_rate", 0.0) or 0.0),
            "tie_rate": float(pairwise_summary.get("tie_rate", 0.0) or 0.0),
            "avg_margin": float(pairwise_summary.get("avg_margin", 0.0) or 0.0),
            "judge_disagreement_rate": float(pairwise_summary.get("judge_disagreement_rate", 0.0) or 0.0),
            "cost_adjusted_value": float(pairwise_summary.get("cost_adjusted_value", 0.0) or 0.0),
        },
        "gate_summary": gate_summary,
        "per_eval": [
            {
                "eval_id": item.get("eval_id"),
                "eval_name": item.get("eval_name", ""),
                "run_number": item.get("run_number"),
                "final_winner": item.get("final_winner", "not_comparable"),
                "avg_margin": float(item.get("avg_margin", 0.0) or 0.0),
                "judge_disagreement": bool(item.get("judge_disagreement", False)),
                "with_skill_run_dir": item.get("with_skill_run_dir", ""),
                "without_skill_run_dir": item.get("without_skill_run_dir", ""),
            }
            for item in pairs
        ],
    }


def _generate_markdown(summary: dict[str, Any]) -> str:
    pairwise = summary["pairwise_summary"]
    lines = [
        "# Level 3 Summary",
        "",
        f"**Generated At**: {summary['metadata']['generated_at']}",
        "",
        "## Primary",
        "",
        f"- Mode: {summary['primary_mode']}",
        f"- Artifact: {summary['primary_artifact_path']}",
        f"- Gate Artifact: {summary['supporting_gate_artifact_path']}",
        "",
        "## Pairwise Summary",
        "",
        f"- Judge strategy: {summary['metadata'].get('judge_strategy', 'unknown')}",
        f"- Win rate: {pairwise['win_rate']:.4f}",
        f"- Tie rate: {pairwise['tie_rate']:.4f}",
        f"- Avg margin: {pairwise['avg_margin']:.4f}",
        f"- Judge disagreement rate: {pairwise['judge_disagreement_rate']:.4f}",
        f"- Cost-adjusted value: {pairwise['cost_adjusted_value']:.4f}",
        "",
        "## Per Eval",
        "",
    ]
    for item in summary["per_eval"]:
        lines.append(
            f"- Eval {item['eval_id']} / run-{item['run_number']}: winner={item['final_winner']}, "
            f"margin={item['avg_margin']:.4f}, disagreement={item['judge_disagreement']}"
        )
    return "\n".join(lines).strip() + "\n"


def write_level3_summary_artifacts(iteration_dir: str | Path, summary: dict[str, Any]) -> dict[str, str]:
    iteration_path = Path(iteration_dir)
    json_path = iteration_path / "level3-summary.json"
    markdown_path = iteration_path / "level3-summary.md"
    write_json(json_path, summary)
    write_text(markdown_path, _generate_markdown(summary))
    return {
        "level3_summary_json": str(json_path),
        "level3_summary_markdown": str(markdown_path),
    }


def ensure_level3_summary(iteration_dir: str | Path) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    summary_path = iteration_path / "level3-summary.json"
    if summary_path.exists():
        return load_json(summary_path)
    summary = generate_level3_summary(iteration_path)
    write_level3_summary_artifacts(iteration_path, summary)
    return summary
