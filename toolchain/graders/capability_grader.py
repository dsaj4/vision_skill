from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from toolchain.common import load_json, write_json


def _find_output_file(outputs_dir: Path) -> Path:
    preferred = outputs_dir / "final_response.md"
    if preferred.exists():
        return preferred

    candidates = sorted(
        path
        for path in outputs_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}
    )
    if not candidates:
        raise FileNotFoundError(f"No response file found in {outputs_dir}")
    return candidates[0]


def _normalize_assertion(assertion: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(assertion, dict):
        return {
            "id": assertion.get("id", ""),
            "type": assertion.get("type", "contains_any"),
            "text": assertion.get("text", assertion.get("id", "Unnamed assertion")),
            "keywords": assertion.get("keywords", []),
            "keyword_groups": assertion.get("keyword_groups", []),
        }

    lowered = assertion.lower()
    if "strengths" in lowered and "weaknesses" in lowered and "opportunities" in lowered and "threats" in lowered:
        return {
            "id": "swot-quadrants",
            "type": "contains_all_groups",
            "text": assertion,
            "keyword_groups": [
                ["strengths", "优势"],
                ["weaknesses", "劣势"],
                ["opportunities", "机会"],
                ["threats", "威胁"],
            ],
        }
    if "all four swot quadrants" in lowered:
        return {
            "id": "swot-quadrants",
            "type": "contains_all_groups",
            "text": assertion,
            "keyword_groups": [
                ["strengths", "优势"],
                ["weaknesses", "劣势"],
                ["opportunities", "机会"],
                ["threats", "威胁"],
            ],
        }
    if "staged interaction pattern" in lowered and "direct-result mode" in lowered:
        return {
            "id": "interaction-mode",
            "type": "staged_or_full_result",
            "text": assertion,
            "pause_markers": ['回复"继续"', '回复"不对"', '回复"直接要结果"', "输出后暂停", "暂停确认"],
            "keyword_groups": [
                ["strengths", "优势"],
                ["weaknesses", "劣势"],
                ["opportunities", "机会"],
                ["threats", "威胁"],
            ],
        }
    if "direct-result" in lowered or "direct result" in lowered:
        return {
            "id": "direct-result-mode",
            "type": "contains_none",
            "text": assertion,
            "keywords": ['回复"继续"', '回复"不对"', '回复"直接要结果"', "输出后暂停", "暂停确认"],
        }
    if "strategy guidance" in lowered or "strategy suggestions" in lowered or "actionable strategy" in lowered:
        return {
            "id": "strategy-guidance",
            "type": "contains_any",
            "text": assertion,
            "keywords": ["strategy", "strategic", "建议", "策略", "行动"],
        }
    if "staged interaction pattern" in lowered:
        return {
            "id": "interaction-mode",
            "type": "contains_any",
            "text": assertion,
            "keywords": ['回复"继续"', '回复"不对"', '回复"直接要结果"', "输出后暂停", "暂停确认"],
        }

    return {
        "id": "",
        "type": "contains_any",
        "text": assertion,
        "keywords": [],
        "keyword_groups": [],
    }


def _evaluate_assertion(assertion: dict[str, Any], response_text: str) -> dict[str, Any]:
    response_lower = response_text.lower()
    assertion_type = assertion.get("type", "contains_any")
    text = assertion.get("text", "")
    expectation_id = assertion.get("id", "")

    if assertion_type == "contains_all":
        keywords = [str(item) for item in assertion.get("keywords", [])]
        matched = [keyword for keyword in keywords if keyword.lower() in response_lower]
        missing = [keyword for keyword in keywords if keyword.lower() not in response_lower]
        passed = len(missing) == 0
        evidence = f"Matched: {matched}; Missing: {missing}"
    elif assertion_type == "staged_or_full_result":
        pause_markers = [str(item) for item in assertion.get("pause_markers", [])]
        groups = [[str(item) for item in group] for group in assertion.get("keyword_groups", [])]
        pause_matches = [marker for marker in pause_markers if marker.lower() in response_lower]
        matched_groups: list[str] = []
        for group in groups:
            if any(keyword.lower() in response_lower for keyword in group):
                matched_groups.append("/".join(group))
        has_full_result = len(matched_groups) == len(groups) and len(groups) > 0
        passed = bool(pause_matches) or has_full_result
        evidence = f"Pause matches: {pause_matches}; Full result groups: {matched_groups}"
    elif assertion_type == "contains_none":
        keywords = [str(item) for item in assertion.get("keywords", [])]
        found = [keyword for keyword in keywords if keyword.lower() in response_lower]
        passed = len(found) == 0
        evidence = f"Forbidden matches: {found}"
    elif assertion_type == "contains_all_groups":
        groups = [[str(item) for item in group] for group in assertion.get("keyword_groups", [])]
        matched_groups: list[str] = []
        missing_groups: list[list[str]] = []
        for group in groups:
            if any(keyword.lower() in response_lower for keyword in group):
                matched_groups.append("/".join(group))
            else:
                missing_groups.append(group)
        passed = len(missing_groups) == 0
        evidence = f"Matched groups: {matched_groups}; Missing groups: {missing_groups}"
    else:
        keywords = [str(item) for item in assertion.get("keywords", [])]
        found = [keyword for keyword in keywords if keyword.lower() in response_lower]
        if keywords:
            passed = len(found) > 0
            evidence = f"Matched: {found}"
        else:
            passed = len(response_text.strip()) > 0
            evidence = "Non-empty response."

    return {
        "id": expectation_id,
        "type": assertion_type,
        "text": text,
        "passed": passed,
        "evidence": evidence,
    }


def grade_response_text(
    response_text: str,
    eval_metadata: dict[str, Any],
    *,
    output_file: str = "<inline-response>",
    timing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assertions = eval_metadata.get("assertions", [])
    expectation_results = [
        _evaluate_assertion(_normalize_assertion(assertion), response_text)
        for assertion in assertions
    ]
    passed = sum(1 for item in expectation_results if item["passed"])
    total = len(expectation_results)
    failed = total - passed
    pass_rate = round(passed / total, 4) if total else 0.0

    metrics = {
        "response_character_count": len(response_text),
        "response_word_count": len(response_text.split()),
        "markdown_heading_count": len(re.findall(r"^#{1,6}\s+", response_text, re.MULTILINE)),
        "total_tool_calls": 0,
        "errors_encountered": 0,
    }

    return {
        "eval_id": eval_metadata.get("eval_id"),
        "eval_name": eval_metadata.get("eval_name", ""),
        "prompt": eval_metadata.get("prompt", ""),
        "output_file": output_file,
        "expectations": expectation_results,
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": pass_rate,
        },
        "execution_metrics": metrics,
        "timing": timing or {},
    }


def grade_run(run_path: str | Path) -> dict[str, Any]:
    run_dir = Path(run_path)
    eval_dir = run_dir.parent.parent
    eval_metadata = load_json(eval_dir / "eval_metadata.json")
    assertions = eval_metadata.get("assertions", [])
    output_file = _find_output_file(run_dir / "outputs")
    response_text = output_file.read_text(encoding="utf-8")

    timing_path = run_dir / "timing.json"
    timing = load_json(timing_path) if timing_path.exists() else {}
    grading = grade_response_text(
        response_text,
        {
            "eval_id": eval_metadata.get("eval_id"),
            "eval_name": eval_metadata.get("eval_name", eval_dir.name),
            "prompt": eval_metadata.get("prompt", ""),
            "assertions": assertions,
        },
        output_file=str(output_file),
        timing=timing,
    )

    write_json(run_dir / "grading.json", grading)
    write_json(run_dir / "metrics.json", grading["execution_metrics"])
    return grading
