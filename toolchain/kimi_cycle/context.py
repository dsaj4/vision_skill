from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from toolchain.common import compact_text, load_json, read_text, write_json, write_text


def find_latest_file(workspace_dir: Path, filename: str) -> Path | None:
    candidates = [path for path in workspace_dir.rglob(filename) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def next_cycle_name(prefix: str = "kimi-cycle") -> str:
    from datetime import datetime

    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _compact_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    cross_eval_summary = analysis.get("cross_eval_summary", {})
    summary_text = str(
        cross_eval_summary.get("critical_issue")
        or cross_eval_summary.get("summary_text")
        or cross_eval_summary.get("critical_pattern")
        or ""
    ).strip()
    return {
        "failure_tag_counts": analysis.get("failure_tag_counts", {}),
        "cross_eval_summary": {
            "overall_winner": cross_eval_summary.get("overall_winner", cross_eval_summary.get("overall_skill_value", "")),
            "summary_text": compact_text(summary_text, 900) if summary_text else "",
        },
        "per_eval": [
            {
                "eval_id": item.get("eval_id"),
                "winner": item.get("winner"),
                "failure_tags": item.get("failure_tags", []),
                "repair_layer": item.get("repair_layer", ""),
                "summary": compact_text(str(item.get("summary", "")).strip(), 240) if item.get("summary") else "",
            }
            for item in analysis.get("per_eval", [])
        ],
    }


def _compact_differential(summary: dict[str, Any]) -> dict[str, Any]:
    root = summary.get("summary", summary)
    rows = summary.get("rows", summary.get("pairs", []))
    return {
        "summary": {
            "pair_count": root.get("pair_count", 0),
            "win_rate": root.get("win_rate", 0.0),
            "loss_rate": root.get("loss_rate", 0.0),
            "tie_rate": root.get("tie_rate", 0.0),
            "avg_margin": root.get("avg_margin", 0.0),
            "with_skill_pass_rate": root.get("with_skill_pass_rate"),
            "without_skill_pass_rate": root.get("without_skill_pass_rate"),
            "cost_adjusted_value": root.get("cost_adjusted_value"),
        },
        "rows": [
            {
                "eval_id": item.get("eval_id"),
                "final_winner": item.get("final_winner", item.get("winner")),
                "avg_margin": item.get("avg_margin", 0.0),
                "with_skill_pass_rate": item.get("with_skill_pass_rate"),
                "without_skill_pass_rate": item.get("without_skill_pass_rate"),
            }
            for item in rows
        ],
    }


def load_recent_cycle_context(workspace_dir: str | Path) -> dict[str, Any]:
    workspace_path = Path(workspace_dir)
    latest_kimi_summary = find_latest_file(workspace_path, "kimi-differential-summary.json")
    latest_differential = find_latest_file(workspace_path, "differential-benchmark.json")
    latest_analysis = find_latest_file(workspace_path, "analysis.json")
    latest_host_benchmark = find_latest_file(workspace_path, "host-benchmark.json")

    context: dict[str, Any] = {
        "latest_kimi_summary_path": str(latest_kimi_summary) if latest_kimi_summary else "",
        "latest_differential_path": str(latest_differential) if latest_differential else "",
        "latest_analysis_path": str(latest_analysis) if latest_analysis else "",
        "latest_host_benchmark_path": str(latest_host_benchmark) if latest_host_benchmark else "",
    }
    if latest_kimi_summary and latest_kimi_summary.exists():
        context["kimi_summary"] = _compact_differential(load_json(latest_kimi_summary))
    if latest_differential and latest_differential.exists():
        context["differential_summary"] = _compact_differential(load_json(latest_differential))
    if latest_analysis and latest_analysis.exists():
        context["analysis"] = _compact_analysis(load_json(latest_analysis))
    if latest_host_benchmark and latest_host_benchmark.exists():
        context["host_benchmark"] = load_json(latest_host_benchmark)
    return context


def compact_json_block(data: dict[str, Any], max_chars: int) -> str:
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return compact_text(serialized, max_chars)
