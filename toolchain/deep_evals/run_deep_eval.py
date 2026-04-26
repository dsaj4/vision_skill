from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from toolchain.common import extract_json_object, write_json, write_text
from toolchain.deep_evals.packet_builder import build_deep_eval_packet
from toolchain.deep_evals.quality_rubric import (
    ALLOWED_QUALITY_DECISIONS,
    ALLOWED_REPAIR_LAYERS,
    DEFAULT_FAILURE_TAG,
    build_rubric_contract,
)
from toolchain.kimi_runtime import CommandRunner
from toolchain.kimi_workspace import load_workspace_json, run_kimi_workspace_task, write_workspace_task


Sender = Callable[[dict[str, Any]], dict[str, Any]]


def _deep_eval_model(explicit: str | None = None) -> str:
    return explicit or os.getenv("VISION_DEEP_EVAL_MODEL") or os.getenv("VISION_ANALYZER_MODEL") or "kimi-cli-default"


def _extract_raw_json(raw_response: dict[str, Any]) -> dict[str, Any]:
    message = raw_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    return extract_json_object(message, error_message="Deep eval response did not contain a JSON object.")


def _normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_repair_layer(value: Any, failure_tags: list[str]) -> str:
    text = str(value or "").strip()
    if text in ALLOWED_REPAIR_LAYERS:
        return text
    if failure_tags and "." in failure_tags[0]:
        prefix = failure_tags[0].split(".", 1)[0]
        if prefix in ALLOWED_REPAIR_LAYERS:
            return prefix
    return "skill-content"


def _normalize_winner(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"with_skill", "without_skill", "tie"}:
        return text
    if text in {"positive", "pass", "skill"}:
        return "with_skill"
    if text in {"negative", "baseline"}:
        return "without_skill"
    return "tie"


def _clamp_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.6
    return round(max(0.0, min(numeric, 1.0)), 4)


def _fallback_per_eval(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "eval_id": item.get("eval_id"),
            "eval_name": item.get("eval_name", ""),
            "winner": "tie",
            "quality_score": None,
            "comparative_judgment": "未获得模型深度判断，保留为人工复核项。",
            "quality_findings": [],
            "failure_tags": [DEFAULT_FAILURE_TAG],
            "repair_layer": "skill-content",
            "evidence_refs": [run.get("run_dir", "") for run in item.get("runs", [])],
            "summary": "缺少结构化 deep eval 输出。",
        }
        for item in packet.get("evals", [])
    ]


def _normalize_per_eval(raw_items: Any, packet: dict[str, Any]) -> list[dict[str, Any]]:
    source_items = raw_items if isinstance(raw_items, list) else []
    if not source_items:
        source_items = _fallback_per_eval(packet)

    eval_names = {item.get("eval_id"): item.get("eval_name", "") for item in packet.get("evals", [])}
    normalized: list[dict[str, Any]] = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        failure_tags = [str(tag) for tag in _normalize_list(item.get("failure_tags")) if str(tag).strip()]
        failed_dimensions = [str(value) for value in _normalize_list(item.get("failed_dimensions")) if str(value).strip()]
        repair_layer = _normalize_repair_layer(item.get("repair_layer"), failure_tags)
        if not failure_tags and _normalize_winner(item.get("winner")) != "with_skill":
            failure_tags = [DEFAULT_FAILURE_TAG]
        if not failed_dimensions and failure_tags:
            failed_dimensions = ["Live Test Performance"]
        normalized.append(
            {
                "eval_id": item.get("eval_id"),
                "eval_name": item.get("eval_name") or eval_names.get(item.get("eval_id"), ""),
                "winner": _normalize_winner(item.get("winner")),
                "quality_score": item.get("quality_score"),
                "dimension_assessments": _normalize_list(item.get("dimension_assessments")),
                "failed_dimensions": failed_dimensions,
                "comparative_judgment": str(
                    item.get("comparative_judgment")
                    or item.get("summary")
                    or item.get("mechanism_findings")
                    or ""
                ).strip(),
                "quality_findings": _normalize_list(
                    item.get("quality_findings", item.get("mechanism_findings", []))
                ),
                "failure_tags": failure_tags,
                "repair_layer": repair_layer,
                "repair_hypothesis": str(item.get("repair_hypothesis", "")).strip(),
                "evidence_refs": _normalize_list(item.get("evidence_refs", item.get("evidence_paths", []))),
                "summary": str(item.get("summary", "")).strip(),
            }
        )
    return normalized


def _normalize_release_signal(raw: Any, per_eval: list[dict[str, Any]]) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    raw_decision = str(source.get("decision", "")).strip()
    if raw_decision not in ALLOWED_QUALITY_DECISIONS:
        winners = {item.get("winner") for item in per_eval}
        if "without_skill" in winners:
            raw_decision = "revise"
        elif winners == {"with_skill"}:
            raw_decision = "pass"
        else:
            raw_decision = "revise"

    reasons = _normalize_list(source.get("reasons"))
    if not reasons and raw_decision != "pass":
        reasons = ["deep quality evaluation requires revision"]

    return {
        "decision": raw_decision,
        "confidence": _clamp_confidence(source.get("confidence", 0.6)),
        "reasons": [str(item) for item in reasons],
    }


def _normalize_deep_eval(raw: dict[str, Any], packet: dict[str, Any], model: str) -> dict[str, Any]:
    per_eval = _normalize_per_eval(raw.get("per_eval"), packet)
    failure_counts: dict[str, int] = {}
    for item in per_eval:
        for tag in item.get("failure_tags", []):
            failure_counts[tag] = failure_counts.get(tag, 0) + 1

    cross_eval_summary = raw.get("cross_eval_summary", {})
    if not isinstance(cross_eval_summary, dict):
        cross_eval_summary = {"summary": str(cross_eval_summary)}

    repair_recommendations = _normalize_list(raw.get("repair_recommendations"))
    release_signal = _normalize_release_signal(raw.get("release_signal"), per_eval)

    return {
        "metadata": {
            "package_name": packet.get("metadata", {}).get("package_name", ""),
            "skill_name": packet.get("metadata", {}).get("skill_name", ""),
            "iteration_dir": packet.get("metadata", {}).get("iteration_dir", ""),
            "deep_eval_model": model,
            "quality_primary_mode": "deep-quality",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "rubric": raw.get("rubric", packet.get("rubric", build_rubric_contract())),
        "per_eval": per_eval,
        "cross_eval_summary": cross_eval_summary,
        "repair_recommendations": repair_recommendations,
        "failure_tag_counts": failure_counts,
        "release_signal": release_signal,
        "evidence_index": {
            "source_packet": "inputs/deep-eval-packet.json",
            "raw_run_artifacts": "iteration eval-* run directories",
        },
    }


def _failure_tags_artifact(deep_eval: dict[str, Any]) -> dict[str, Any]:
    return {
        "metadata": {
            "generated_at": deep_eval["metadata"]["generated_at"],
            "source_artifact": "deep-eval.json",
        },
        "counts": deep_eval.get("failure_tag_counts", {}),
        "per_eval": [
            {
                "eval_id": item.get("eval_id"),
                "failure_tags": item.get("failure_tags", []),
                "repair_layer": item.get("repair_layer", "skill-content"),
            }
            for item in deep_eval.get("per_eval", [])
        ],
    }


def _markdown(deep_eval: dict[str, Any]) -> str:
    signal = deep_eval.get("release_signal", {})
    lines = [
        "# Deep Quality Eval",
        "",
        f"**Model**: {deep_eval['metadata']['deep_eval_model']}",
        f"**Decision Signal**: {signal.get('decision', 'revise')}",
        f"**Confidence**: {signal.get('confidence', 0.0)}",
        "",
        "## Cross Eval Summary",
        "",
    ]
    summary = deep_eval.get("cross_eval_summary", {})
    if summary:
        for key, value in summary.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- n/a")

    lines.extend(["", "## Per Eval", ""])
    for item in deep_eval.get("per_eval", []):
        lines.extend(
            [
                f"### Eval {item.get('eval_id')}: {item.get('eval_name', '')}",
                f"- Winner: {item.get('winner', 'tie')}",
                f"- Repair Layer: {item.get('repair_layer', 'skill-content')}",
                f"- Failed Dimensions: {', '.join(item.get('failed_dimensions', [])) if item.get('failed_dimensions') else 'none'}",
                f"- Failure Tags: {', '.join(item.get('failure_tags', [])) if item.get('failure_tags') else 'none'}",
                f"- Summary: {item.get('summary') or item.get('comparative_judgment') or 'n/a'}",
                "",
            ]
        )

    lines.extend(["## Repair Recommendations", ""])
    recommendations = deep_eval.get("repair_recommendations", [])
    if not recommendations:
        lines.append("- none")
    else:
        for item in recommendations:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def _workspace_contract() -> str:
    return "\n".join(
        [
            "# Output Contract",
            "",
            "Required file: `outputs/deep-eval.json`.",
            "",
            "JSON object keys:",
            "",
            "- `per_eval`",
            "- `cross_eval_summary`",
            "- `repair_recommendations`",
            "- `release_signal`",
            "- Optional but preferred per-eval keys: `dimension_assessments`, `failed_dimensions`, `repair_hypothesis`.",
            "",
            "`release_signal.decision` must be one of `pass`, `revise`, `hold`.",
            "`repair_layer` must be one of `source`, `blueprint-spec`, `template`, `skill-content`.",
            "All written report text should be Chinese.",
        ]
    )


def _workspace_task_markdown() -> str:
    return "\n".join(
        [
            "# Controlled Deep Quality Eval Task",
            "",
            "This is a workspace-file task. The terminal response is log-only.",
            "",
            "## Inputs",
            "",
            "- Read `inputs/deep-eval-packet.json`.",
            "- Judge quality directly from with_skill / without_skill raw answers and run artifacts.",
            "- Do not use benchmark or differential numbers as the main conclusion; they are supporting context only.",
            "",
            "## Conservative Rubric Policy",
            "",
            "- First-stage deep eval uses only Darwin dimensions that map clearly to content quality.",
            "- Primary deep dimensions: `Overall Structure` and `Live Test Performance`.",
            "- Frontmatter, path checks, resource references, checkpoint counts, and other countable signals belong to `quantitative-summary.json`, not deep quality judgment.",
            "- Failure attribution must stay inside `source`, `blueprint-spec`, `template`, `skill-content`.",
            "",
            "## Required Output",
            "",
            "Write only `outputs/deep-eval.json`. Report text inside JSON should be Chinese.",
            "Do not put the JSON in the terminal response.",
        ]
    )


def _run_workspace_deep_eval(
    packet: dict[str, Any],
    *,
    task_dir: Path,
    deep_eval_model: str | None,
    timeout_seconds: int | None,
    command_runner: CommandRunner | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    required_outputs = ["outputs/deep-eval.json"]
    write_workspace_task(
        task_dir,
        task_markdown=_workspace_task_markdown(),
        required_outputs=required_outputs,
        contract_markdown=_workspace_contract(),
        inputs={"inputs/deep-eval-packet.json": packet},
        metadata={
            "runner": "kimi-code",
            "task_type": "deep-quality-eval",
            "package_name": packet.get("metadata", {}).get("package_name", ""),
        },
    )
    task_result = run_kimi_workspace_task(
        task_dir,
        required_outputs=required_outputs,
        model=deep_eval_model,
        timeout_seconds=timeout_seconds,
        command_runner=command_runner,
    )
    return load_workspace_json(task_result, "outputs/deep-eval.json"), task_result


def run_deep_eval(
    iteration_dir: str | Path,
    package_dir: str | Path,
    *,
    sender: Sender | None = None,
    command_runner: CommandRunner | None = None,
    deep_eval_model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    packet = build_deep_eval_packet(iteration_path, package_path)
    model = _deep_eval_model(deep_eval_model)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是 Vision Skill 深度质量评测员。"
                    "只返回 JSON，字段包含 per_eval, cross_eval_summary, repair_recommendations, release_signal。"
                    "所有结论与 report 文本使用中文。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(packet, ensure_ascii=False, separators=(",", ":")),
            },
        ],
    }

    if sender is not None:
        raw_response = sender(payload)
        raw_deep_eval = _extract_raw_json(raw_response)
    else:
        raw_deep_eval, task_result = _run_workspace_deep_eval(
            packet,
            task_dir=iteration_path / ".kimi-deep-eval",
            deep_eval_model=deep_eval_model,
            timeout_seconds=timeout_seconds,
            command_runner=command_runner,
        )
        raw_response = {
            "choices": [{"message": {"role": "assistant", "content": json.dumps(raw_deep_eval, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "kimi_workspace_task": {
                "task_dir": task_result.get("work_dir", ""),
                "resolved_outputs": task_result.get("resolved_outputs", {}),
                "terminal_response_policy": "log-only",
                "warnings": task_result.get("warnings", []),
                "stderr": task_result.get("stderr", ""),
            },
        }

    deep_eval = _normalize_deep_eval(raw_deep_eval, packet, model)
    failure_tags = _failure_tags_artifact(deep_eval)

    write_json(iteration_path / "deep-eval.json", deep_eval)
    write_text(iteration_path / "deep-eval.md", _markdown(deep_eval))
    write_json(iteration_path / "quality-failure-tags.json", failure_tags)

    return {
        "packet": packet,
        "deep_eval": deep_eval,
        "failure_tags": failure_tags,
        "raw_response": raw_response,
        "artifacts": {
            "deep_eval_json": str(iteration_path / "deep-eval.json"),
            "deep_eval_markdown": str(iteration_path / "deep-eval.md"),
            "quality_failure_tags_json": str(iteration_path / "quality-failure-tags.json"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deep quality evaluation for a Vision Skill iteration.")
    parser.add_argument("--iteration-dir", required=True, help="Path to the iteration directory.")
    parser.add_argument("--package-dir", required=True, help="Path to the package directory.")
    parser.add_argument("--deep-eval-model", default=None, help="Optional deep eval model override.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional timeout override.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_deep_eval(
        args.iteration_dir,
        args.package_dir,
        deep_eval_model=args.deep_eval_model,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
