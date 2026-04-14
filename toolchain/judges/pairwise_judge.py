from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from toolchain.executors.dashscope_executor import (
    _post_chat_completion,
    _resolve_api_key,
    _resolve_endpoint,
    _resolve_model,
    _resolve_timeout,
)


RUBRIC_DIMENSIONS = [
    "Thinking Support",
    "Tradeoff Quality",
    "Actionability",
    "Judgment Preservation",
    "Boundary Safety",
]

DEFAULT_MARGIN = 0.0
DEFAULT_CONFIDENCE = 0.0

Sender = Callable[[dict[str, Any], str, str, int], dict[str, Any]]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_response(run_dir: Path) -> str:
    grading_path = run_dir / "grading.json"
    if grading_path.exists():
        grading = _load_json(grading_path)
        output_file = Path(grading.get("output_file", ""))
        if output_file.exists():
            return output_file.read_text(encoding="utf-8")
    output_file = run_dir / "outputs" / "final_response.md"
    if output_file.exists():
        return output_file.read_text(encoding="utf-8")
    return ""


def _extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Judge response did not contain a JSON object.")
    return json.loads(candidate[start : end + 1])


def _clamp_score(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(numeric, 1.0)), 4)


def _normalize_side(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"a", "candidate_a", "candidate a"}:
        return "A"
    if text in {"b", "candidate_b", "candidate b"}:
        return "B"
    if text in {"tie", "equal"}:
        return "tie"
    if text in {"not_comparable", "not comparable"}:
        return "not_comparable"
    return "tie"


def _normalize_winner(side: str, orientation: str) -> str:
    if side in {"tie", "not_comparable"}:
        return side
    if orientation == "forward":
        return "with_skill" if side == "A" else "without_skill"
    if orientation == "reversed":
        return "without_skill" if side == "A" else "with_skill"
    return "with_skill" if side == "A" else "without_skill"


def _normalize_rubric(raw: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for dimension in RUBRIC_DIMENSIONS:
        normalized[dimension] = _normalize_side(raw.get(dimension, "tie"))
    return normalized


def _gate_check(run_dir: Path) -> dict[str, Any]:
    reasons: list[str] = []
    response_text = _read_response(run_dir)
    grading_path = run_dir / "grading.json"
    metrics = {}
    if grading_path.exists():
        metrics = _load_json(grading_path).get("execution_metrics", {})

    if not response_text.strip():
        reasons.append("empty_response")
    if int(metrics.get("errors_encountered", 0) or 0) > 0:
        reasons.append("execution_errors")

    return {
        "comparable": len(reasons) == 0,
        "reasons": reasons,
        "response_text": response_text,
    }


def _load_cost(run_dir: Path) -> dict[str, float]:
    timing_path = run_dir / "timing.json"
    timing = _load_json(timing_path) if timing_path.exists() else {}
    return {
        "time_seconds": float(timing.get("total_duration_seconds", 0.0) or 0.0),
        "tokens": float(timing.get("total_tokens", 0) or 0),
    }


def _build_packet(
    *,
    prompt: str,
    eval_id: int,
    eval_name: str,
    run_number: int,
    orientation: str,
    candidate_a: dict[str, Any],
    candidate_b: dict[str, Any],
) -> dict[str, Any]:
    return {
        "eval_id": eval_id,
        "eval_name": eval_name,
        "run_number": run_number,
        "orientation": orientation,
        "task_prompt": prompt,
        "rubric": RUBRIC_DIMENSIONS,
        "comparison_rules": [
            "Judge user value, not verbosity or formatting polish.",
            "Allow diverse answers if both are genuinely helpful.",
            "Return tie when neither answer is clearly better.",
            "Do not reveal or assume which answer used the skill.",
        ],
        "candidate_a": candidate_a,
        "candidate_b": candidate_b,
    }


def _build_messages(packet: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a strict pairwise judge for AI assistant answers. "
                "Compare Candidate A and Candidate B only on user value. "
                "Return only JSON with keys: winner, margin, confidence, reasoning_summary, rubric_winner_by_dimension. "
                "winner must be one of: A, B, tie. "
                "margin and confidence must be between 0 and 1. "
                "rubric_winner_by_dimension must use only A, B, or tie."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(packet, ensure_ascii=False, indent=2),
        },
    ]


def judge_pair(
    *,
    eval_id: int,
    eval_name: str,
    prompt: str,
    run_number: int,
    with_skill_run_dir: str | Path,
    without_skill_run_dir: str | Path,
    orientation: str = "forward",
    sender: Sender | None = None,
    api_key: str | None = None,
    judge_model: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    with_skill_path = Path(with_skill_run_dir)
    without_skill_path = Path(without_skill_run_dir)
    with_skill_gate = _gate_check(with_skill_path)
    without_skill_gate = _gate_check(without_skill_path)

    if orientation == "forward":
        candidate_a = {
            "configuration": "with_skill",
            "response": with_skill_gate["response_text"],
            "run_dir": str(with_skill_path),
        }
        candidate_b = {
            "configuration": "without_skill",
            "response": without_skill_gate["response_text"],
            "run_dir": str(without_skill_path),
        }
    else:
        candidate_a = {
            "configuration": "without_skill",
            "response": without_skill_gate["response_text"],
            "run_dir": str(without_skill_path),
        }
        candidate_b = {
            "configuration": "with_skill",
            "response": with_skill_gate["response_text"],
            "run_dir": str(with_skill_path),
        }

    pair_cost = {
        "with_skill": _load_cost(with_skill_path),
        "without_skill": _load_cost(without_skill_path),
    }
    gate_check = {
        "comparable": with_skill_gate["comparable"] and without_skill_gate["comparable"],
        "reasons": sorted(set(with_skill_gate["reasons"] + without_skill_gate["reasons"])),
    }

    result = {
        "metadata": {
            "eval_id": eval_id,
            "eval_name": eval_name,
            "run_number": run_number,
            "orientation": orientation,
            "judge_model": judge_model or os.getenv("VISION_JUDGE_MODEL") or _resolve_model(None),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "pair": {
            "candidate_a": {"configuration": candidate_a["configuration"], "run_dir": candidate_a["run_dir"]},
            "candidate_b": {"configuration": candidate_b["configuration"], "run_dir": candidate_b["run_dir"]},
        },
        "rubric": RUBRIC_DIMENSIONS,
        "gate_check": gate_check,
        "cost": pair_cost,
        "judgment": {
            "winner": "not_comparable",
            "normalized_winner": "not_comparable",
            "margin": DEFAULT_MARGIN,
            "confidence": DEFAULT_CONFIDENCE,
            "reasoning_summary": "Pair failed gate check and was not judged.",
            "rubric_winner_by_dimension": {dimension: "tie" for dimension in RUBRIC_DIMENSIONS},
        },
    }

    if not gate_check["comparable"]:
        return result

    packet = _build_packet(
        prompt=prompt,
        eval_id=eval_id,
        eval_name=eval_name,
        run_number=run_number,
        orientation=orientation,
        candidate_a=candidate_a,
        candidate_b=candidate_b,
    )
    payload = {
        "model": result["metadata"]["judge_model"],
        "messages": _build_messages(packet),
    }
    raw_response = (sender or _post_chat_completion)(
        payload,
        _resolve_endpoint(endpoint),
        _resolve_api_key(api_key),
        _resolve_timeout(timeout_seconds),
    )
    message = raw_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    raw_judgment = _extract_json_object(message)
    winner = _normalize_side(raw_judgment.get("winner", "tie"))
    rubric = _normalize_rubric(raw_judgment.get("rubric_winner_by_dimension", {}))

    result["judgment"] = {
        "winner": winner,
        "normalized_winner": _normalize_winner(winner, orientation),
        "margin": _clamp_score(raw_judgment.get("margin", DEFAULT_MARGIN)),
        "confidence": _clamp_score(raw_judgment.get("confidence", DEFAULT_CONFIDENCE)),
        "reasoning_summary": str(raw_judgment.get("reasoning_summary", "")).strip(),
        "rubric_winner_by_dimension": rubric,
    }
    return result
