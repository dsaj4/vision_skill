from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from toolchain.benchmarks.level3_summary import ensure_level3_summary
from toolchain.executors.dashscope_executor import (
    _post_chat_completion,
    _resolve_api_key,
    _resolve_endpoint,
    _resolve_model,
    _resolve_timeout,
)


Sender = Callable[[dict[str, Any], str, str, int], dict[str, Any]]
ALLOWED_REPAIR_LAYERS = {"source", "blueprint-spec", "template", "skill-content"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _truncate(text: str, limit: int = 1600) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 15] + "\n...[truncated]"


def _extract_markdown_section(content: str, titles: list[str]) -> str:
    joined = "|".join(re.escape(title) for title in titles)
    pattern = re.compile(rf"^(?:{joined}).*?(?=^##\s|^###\s|\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(content)
    return match.group(0).strip() if match else ""


def _extract_step(content: str, step_number: int) -> str:
    pattern = re.compile(
        rf"^### Step {step_number}:?.*?(?=^### Step \d+:?.*|^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(0).strip() if match else ""


def _load_taxonomy(taxonomy: dict[str, Any] | None = None) -> dict[str, Any]:
    if taxonomy is not None:
        return taxonomy
    taxonomy_path = Path(__file__).resolve().parents[2] / "shared" / "review-templates" / "failure-taxonomy-v0.1.json"
    if taxonomy_path.exists():
        return _load_json(taxonomy_path)
    return {"categories": []}


def _collect_allowed_failure_tags(taxonomy: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    for category in taxonomy.get("categories", []):
        for subcategory in category.get("subcategories", []):
            if "id" in subcategory:
                tags.add(subcategory["id"])
    return tags


def _extract_skill_mechanisms(skill_text: str) -> dict[str, Any]:
    return {
        "interaction_mode": _extract_markdown_section(skill_text, ["## 交互模式", "## Interaction Mode"]),
        "step_0": _extract_step(skill_text, 0),
        "step_1": _extract_step(skill_text, 1),
        "step_2": _extract_step(skill_text, 2),
        "step_3": _extract_step(skill_text, 3),
        "rules": _extract_markdown_section(skill_text, ["## 规则", "## Rules"]),
        "output_format": _extract_markdown_section(skill_text, ["## 输出格式", "## Output Format"]),
    }


def _run_signal_from_response(response_text: str) -> dict[str, Any]:
    lowered = response_text.lower()
    has_structured_output = len(re.findall(r"^#{1,6}\s+", response_text, re.MULTILINE)) > 0
    pause_markers = ['回复"继续"', '回复"不对"', '回复"直接要结果"', "输出后暂停", "暂停确认"]
    has_pause_markers = any(marker.lower() in lowered for marker in pause_markers)
    has_quadrants = all(keyword in lowered for keyword in ("strength", "weak", "opportun", "threat")) or all(
        keyword in response_text for keyword in ("优势", "劣势", "机会", "威胁")
    )
    guardrail_signal = any(keyword in response_text for keyword in ("高压", "减压", "脆弱", "先稳住", "先不要"))
    return {
        "has_structured_output": has_structured_output,
        "has_pause_markers": has_pause_markers,
        "direct_result_mode_detected": has_quadrants and not has_pause_markers,
        "guardrail_signal_present": guardrail_signal,
        "output_length_bucket": "short" if len(response_text) < 600 else "medium" if len(response_text) < 1500 else "long",
    }


def _load_run_record(run_dir: Path, pairwise_outcome: dict[str, Any] | None = None) -> dict[str, Any]:
    grading = _load_json(run_dir / "grading.json")
    transcript = _load_json(run_dir / "transcript.json")
    request = _load_json(run_dir / "request.json")
    timing = _load_json(run_dir / "timing.json")
    response_text = Path(grading["output_file"]).read_text(encoding="utf-8")

    return {
        "run_number": int(run_dir.name.split("-")[1]),
        "path": str(run_dir),
        "pass_rate": grading["summary"].get("pass_rate", 0.0),
        "timing": timing,
        "expectations": grading.get("expectations", []),
        "mechanism_signals": _run_signal_from_response(response_text),
        "pairwise_outcome": pairwise_outcome or {},
        "request_excerpt": _truncate(json.dumps(request, ensure_ascii=False, indent=2), 1200),
        "assistant_excerpt": _truncate(transcript.get("assistant_response", response_text), 1200),
        "evidence_paths": {
            "grading": str(run_dir / "grading.json"),
            "transcript": str(run_dir / "transcript.json"),
            "request": str(run_dir / "request.json"),
            "raw_response": str(run_dir / "raw_response.json"),
            "timing": str(run_dir / "timing.json"),
        },
    }


def build_analysis_packet(
    iteration_dir: Path,
    package_dir: Path,
    taxonomy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    benchmark = _load_json(iteration_path / "benchmark.json")
    stability = _load_json(iteration_path / "stability.json")
    level3_summary = ensure_level3_summary(iteration_path)
    taxonomy_data = _load_taxonomy(taxonomy)
    skill_text = (package_path / "SKILL.md").read_text(encoding="utf-8")
    pairwise_index = {
        (int(item["eval_id"]), int(item["run_number"])): item
        for item in level3_summary.get("per_eval", [])
        if item.get("eval_id") is not None and item.get("run_number") is not None
    }

    evals: list[dict[str, Any]] = []
    for eval_dir in sorted(iteration_path.glob("eval-*")):
        eval_metadata = _load_json(eval_dir / "eval_metadata.json")
        stability_match = next((item for item in stability.get("per_eval", []) if item["eval_id"] == eval_metadata["eval_id"]), {})
        eval_pairwise = [item for item in level3_summary.get("per_eval", []) if item.get("eval_id") == eval_metadata["eval_id"]]
        eval_record = {
            "eval_id": eval_metadata["eval_id"],
            "eval_name": eval_metadata.get("eval_name", eval_dir.name),
            "prompt": eval_metadata.get("prompt", ""),
            "expected_output": eval_metadata.get("expected_output", ""),
            "with_skill_runs": [],
            "without_skill_runs": [],
            "pairwise_results": eval_pairwise,
            "stability_flags": stability_match.get("flags", []),
        }
        for configuration in ("with_skill", "without_skill"):
            config_dir = eval_dir / configuration
            if not config_dir.exists():
                continue
            for run_dir in sorted(config_dir.glob("run-*")):
                if not (run_dir / "grading.json").exists():
                    continue
                pairwise_outcome = pairwise_index.get((int(eval_metadata["eval_id"]), int(run_dir.name.split("-")[1])))
                eval_record[f"{configuration}_runs"].append(_load_run_record(run_dir, pairwise_outcome=pairwise_outcome))
        evals.append(eval_record)

    return {
        "metadata": {
            "package_name": package_path.name,
            "skill_name": level3_summary.get("metadata", {}).get("skill_name", package_path.name),
            "iteration_dir": str(iteration_path),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "skill_mechanisms": _extract_skill_mechanisms(skill_text),
        "level3_summary": level3_summary,
        "gate_summary": level3_summary.get("gate_summary", benchmark.get("run_summary", {})),
        "stability_summary": stability.get("overall", {}),
        "evals": evals,
        "failure_taxonomy": taxonomy_data,
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Analyzer response did not contain a JSON object.")
    return json.loads(candidate[start : end + 1])


def _normalize_cross_eval_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        return {
            "summary_text": stripped,
            "critical_issue": stripped,
        }
    return {}


def _normalize_repair_recommendations(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _normalize_per_eval_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalize_analysis(raw: dict[str, Any], taxonomy: dict[str, Any], analyzer_model: str) -> dict[str, Any]:
    repair_recommendations = _normalize_repair_recommendations(raw.get("repair_recommendations", []))
    cross_eval_summary = _normalize_cross_eval_summary(raw.get("cross_eval_summary", {}))
    per_eval_items = _normalize_per_eval_items(raw.get("per_eval", []))
    allowed_failure_tags = _collect_allowed_failure_tags(taxonomy)
    recommendation_tags = [
        recommendation.get("category") or recommendation.get("issue_id")
        for recommendation in repair_recommendations
        if isinstance(recommendation, dict) and (recommendation.get("category") or recommendation.get("issue_id")) in allowed_failure_tags
    ]
    fallback_layer = ""
    for recommendation in repair_recommendations:
        if not isinstance(recommendation, dict):
            continue
        if recommendation.get("repair_layer") in ALLOWED_REPAIR_LAYERS:
            fallback_layer = recommendation["repair_layer"]
            break
        category = recommendation.get("category", "")
        if "." in category and category.split(".", 1)[0] in ALLOWED_REPAIR_LAYERS:
            fallback_layer = category.split(".", 1)[0]
            break

    per_eval: list[dict[str, Any]] = []
    failure_counts: dict[str, int] = {}

    for item in per_eval_items:
        failure_tags = [tag for tag in item.get("failure_tags", []) if tag in allowed_failure_tags]
        if not failure_tags and recommendation_tags:
            failure_tags = recommendation_tags[:1]
        repair_layer = item.get("repair_layer", "")
        if repair_layer not in ALLOWED_REPAIR_LAYERS:
            if failure_tags:
                repair_layer = failure_tags[0].split(".", 1)[0]
            elif fallback_layer:
                repair_layer = fallback_layer
            else:
                repair_layer = "skill-content"
        for tag in failure_tags:
            failure_counts[tag] = failure_counts.get(tag, 0) + 1

        winner = item.get("winner", "")
        if winner not in {"with_skill", "without_skill", "tie"}:
            overall_skill_value = cross_eval_summary.get("overall_skill_value", "")
            if overall_skill_value == "positive":
                winner = "with_skill"
            elif overall_skill_value == "negative":
                winner = "without_skill"
            else:
                winner = "tie"

        summary = item.get("summary", "")
        if not summary:
            summary = (
                cross_eval_summary.get("critical_issue")
                or cross_eval_summary.get("critical_pattern")
                or cross_eval_summary.get("pattern")
                or cross_eval_summary.get("recommendation")
                or ""
            )

        per_eval.append(
            {
                "eval_id": item.get("eval_id"),
                "winner": winner,
                "mechanism_findings": item.get("mechanism_findings", []),
                "instruction_use_signals": item.get("instruction_use_signals", []),
                "failure_tags": failure_tags,
                "repair_layer": repair_layer,
                "summary": summary,
            }
        )

    if not failure_counts and recommendation_tags:
        for tag in recommendation_tags:
            failure_counts[tag] = failure_counts.get(tag, 0) + 1

    return {
        "metadata": {
            "analyzer_model": analyzer_model,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "per_eval": per_eval,
        "cross_eval_summary": cross_eval_summary,
        "repair_recommendations": repair_recommendations,
        "failure_tag_counts": failure_counts,
    }


def _analysis_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# Mechanism Analysis",
        "",
        f"**Analyzer Model**: {analysis['metadata']['analyzer_model']}",
        "",
        "## Per Eval",
        "",
    ]
    for item in analysis["per_eval"]:
        lines.extend(
            [
                f"### Eval {item['eval_id']}",
                f"- Winner: {item['winner']}",
                f"- Repair Layer: {item['repair_layer']}",
                f"- Failure Tags: {', '.join(item['failure_tags']) if item['failure_tags'] else 'none'}",
                f"- Summary: {item['summary'] or 'n/a'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Cross Eval Summary",
            "",
            f"- Overall Winner: {analysis.get('cross_eval_summary', {}).get('overall_winner', analysis.get('cross_eval_summary', {}).get('overall_skill_value', 'n/a'))}",
            f"- Key Patterns: {analysis.get('cross_eval_summary', {}).get('key_patterns', analysis.get('cross_eval_summary', {}).get('pattern', analysis.get('cross_eval_summary', {}).get('critical_pattern', [])))}",
            f"- Critical Risks: {analysis.get('cross_eval_summary', {}).get('critical_risks', analysis.get('cross_eval_summary', {}).get('critical_issue', analysis.get('cross_eval_summary', {}).get('stability_concern', [])))}",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def analyze_iteration(
    iteration_dir: Path,
    package_dir: Path,
    *,
    taxonomy: dict[str, Any] | None = None,
    analyzer_model: str | None = None,
    sender: Sender | None = None,
    api_key: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    package_path = Path(package_dir)
    taxonomy_data = _load_taxonomy(taxonomy)
    packet = build_analysis_packet(iteration_path, package_path, taxonomy=taxonomy_data)

    model = analyzer_model or os.getenv("VISION_ANALYZER_MODEL") or _resolve_model(None)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are analyzing AI skill evaluation artifacts. "
                    "Return only JSON with keys: per_eval, cross_eval_summary, repair_recommendations. "
                    "repair_layer must be one of: source, blueprint-spec, template, skill-content."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(packet, ensure_ascii=False, indent=2),
            },
        ],
    }

    raw_response = (sender or _post_chat_completion)(
        payload,
        _resolve_endpoint(endpoint),
        _resolve_api_key(api_key),
        _resolve_timeout(timeout_seconds),
    )
    message = raw_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    raw_analysis = _extract_json_object(message)
    analysis = _normalize_analysis(raw_analysis, taxonomy_data, model)

    failure_tags = {
        "metadata": {"generated_at": analysis["metadata"]["generated_at"]},
        "counts": analysis["failure_tag_counts"],
        "per_eval": [
            {
                "eval_id": item["eval_id"],
                "failure_tags": item["failure_tags"],
                "repair_layer": item["repair_layer"],
            }
            for item in analysis["per_eval"]
        ],
    }

    _write_json(iteration_path / "analysis.json", analysis)
    (iteration_path / "analysis.md").write_text(_analysis_markdown(analysis), encoding="utf-8")
    _write_json(iteration_path / "failure-tags.json", failure_tags)

    return {
        "packet": packet,
        "analysis": analysis,
        "failure_tags": failure_tags,
        "raw_response": raw_response,
    }
