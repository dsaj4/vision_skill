from __future__ import annotations

import json
from typing import Any

from toolchain.agent_hosts.event_normalizer import (
    MAX_EVIDENCE_SNIPPETS_PER_EVAL,
    MAX_HOST_PACKET_CHARS,
    PROMPT_BUDGET,
    clean_text_fragment,
)


CHECKPOINT_MARKERS = [
    "pause for confirmation",
    "checkpoint",
    "reply \"continue\"",
    "reply \"revise\"",
]
CONTINUE_KEYWORDS = ["continue", "go on", "next step"]
REVISE_KEYWORDS = ["not right", "revise", "change this", "modify"]
DIRECT_RESULT_KEYWORDS = ["direct result", "give me the swot directly", "do not confirm", "do not pause", "skip checkpoint", "directly"]
MISSING_INFO_KEYWORDS = ["missing information", "need more context", "before i can", "what is your", "which role"]
SWOT_GROUPS = [
    ["strength"],
    ["weakness"],
    ["opportun"],
    ["threat"],
]
STRATEGY_KEYWORDS = ["strategy", "next step", "recommendation", "action plan"]
BINARY_PUSH_KEYWORDS = ["all in", "just quit", "must quit", "immediately resign"]


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _count_matches(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)


def _has_swot_structure(text: str) -> bool:
    lowered = text.lower()
    return all(any(keyword in lowered for keyword in group) for group in SWOT_GROUPS)


def _strategy_present(text: str) -> bool:
    return _contains_any(text, STRATEGY_KEYWORDS)


def _first_assistant_turn(transcript: dict[str, Any]) -> tuple[int | None, str]:
    for turn in transcript.get("turns", []):
        assistant_text = str(turn.get("assistant_text", "")).strip()
        if assistant_text:
            return int(turn.get("turn_index", 0) or 0), assistant_text
    return None, ""


def _first_skill_read_turn(normalized_events: dict[str, Any]) -> int | None:
    turns = [
        int(event["turn_index"])
        for event in normalized_events.get("events", [])
        if event["event_type"] in {"skill_proxy_read", "skill_canonical_read", "skill_meta_read"}
    ]
    return min(turns) if turns else None


def _top_evidence_snippets(normalized_events: dict[str, Any]) -> list[dict[str, Any]]:
    priority_order = {
        "skill_proxy_read": 0,
        "skill_canonical_read": 1,
        "skill_meta_read": 2,
        "agent_message": 3,
        "host_status_message": 4,
        "plugin_interference": 5,
        "network_interference": 6,
        "noise_warning": 7,
        "command_completed": 8,
        "command_started": 9,
    }
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for event in sorted(
        normalized_events.get("events", []),
        key=lambda item: (priority_order.get(item["event_type"], 99), int(item["turn_index"]), item["raw_ref"]),
    ):
        if not event.get("evidence_text"):
            continue
        key = (str(event["event_type"]), str(event["evidence_text"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            {
                "label": event["event_type"],
                "turn_index": int(event["turn_index"]),
                "raw_ref": event["raw_ref"],
                "text": clean_text_fragment(str(event["evidence_text"])),
                "is_noise": bool(event.get("is_noise", False)),
            }
        )
        if len(deduped) >= MAX_EVIDENCE_SNIPPETS_PER_EVAL:
            break
    return deduped


def _fit_packet(packet: dict[str, Any], *, max_chars: int = MAX_HOST_PACKET_CHARS) -> tuple[dict[str, Any], int]:
    working = dict(packet)
    snippets = list(working.get("evidence_snippets", []))
    serialized = json.dumps(working, ensure_ascii=False, separators=(",", ":"))
    while len(serialized) > max_chars and snippets:
        snippets.pop()
        working["evidence_snippets"] = snippets
        serialized = json.dumps(working, ensure_ascii=False, separators=(",", ":"))
    return working, len(serialized)


def extract_host_signals(transcript: dict[str, Any], normalized_events: dict[str, Any]) -> dict[str, Any]:
    turns = list(transcript.get("turns", []))
    first_answer_turn_index, first_answer_text = _first_assistant_turn(transcript)
    first_skill_read_turn_index = _first_skill_read_turn(normalized_events)
    all_assistant_text = "\n\n".join(str(turn.get("assistant_text", "")) for turn in turns if turn.get("assistant_text"))
    normalized_event_items = list(normalized_events.get("events", []))

    proxy_reads = [item for item in normalized_event_items if item["event_type"] == "skill_proxy_read"]
    canonical_reads = [item for item in normalized_event_items if item["event_type"] == "skill_canonical_read"]
    meta_reads = [item for item in normalized_event_items if item["event_type"] == "skill_meta_read"]
    status_messages = [item for item in normalized_event_items if item["event_type"] == "host_status_message"]
    noise_events = [item for item in normalized_event_items if item.get("is_noise")]
    first_answer_lower = first_answer_text.lower()
    first_user_lower = str(turns[0].get("user_text", "")).lower() if turns else ""

    trigger_signals = {
        "proxy_skill_read": bool(proxy_reads),
        "canonical_skill_read": bool(canonical_reads),
        "skill_meta_read": bool(meta_reads),
        "explicit_skill_use_announcement": any("skill" in item["evidence_text"].lower() for item in status_messages),
        "skill_read_before_first_answer": bool(
            first_skill_read_turn_index is not None
            and first_answer_turn_index is not None
            and first_skill_read_turn_index <= first_answer_turn_index
        ),
        "trigger_turn_index": min(
            [int(item["turn_index"]) for item in proxy_reads + canonical_reads + meta_reads],
            default=None,
        ),
        "first_answer_turn_index": first_answer_turn_index,
        "first_skill_read_turn_index": first_skill_read_turn_index,
    }

    routing_signals = {
        "read_using_superpowers": any("using-superpowers" in item["evidence_text"].lower() for item in normalized_event_items),
        "read_proxy_before_canonical": bool(
            proxy_reads and canonical_reads and int(proxy_reads[0]["turn_index"]) <= int(canonical_reads[0]["turn_index"])
        ),
        "read_canonical_multiple_times": len(canonical_reads) > 1,
        "fallback_without_canonical_read": bool(proxy_reads and not canonical_reads),
        "first_answer_before_skill_read": bool(
            first_answer_turn_index is not None
            and first_skill_read_turn_index is not None
            and first_answer_turn_index < first_skill_read_turn_index
        ),
    }

    followup_question_count = first_answer_text.count("?") + first_answer_text.count("？")
    checkpoint_count = _count_matches(all_assistant_text, CHECKPOINT_MARKERS)
    continue_branch_seen = any(_contains_any(str(turn.get("user_text", "")).lower(), CONTINUE_KEYWORDS) for turn in turns[1:])
    revise_branch_seen = any(_contains_any(str(turn.get("user_text", "")).lower(), REVISE_KEYWORDS) for turn in turns[1:])
    direct_result_request_seen = _contains_any(first_user_lower, DIRECT_RESULT_KEYWORDS)
    missing_info_detected = _contains_any(first_answer_lower, MISSING_INFO_KEYWORDS) or followup_question_count > 0
    swot_quadrants_present = _has_swot_structure(all_assistant_text)
    first_answer_swot = _has_swot_structure(first_answer_text)
    strategy_section_present = _strategy_present(all_assistant_text)

    protocol_signals = {
        "followup_question_count": followup_question_count,
        "checkpoint_count": checkpoint_count,
        "continue_branch_seen": continue_branch_seen,
        "revise_branch_seen": revise_branch_seen,
        "direct_result_request_seen": direct_result_request_seen,
        "direct_result_obeyed": bool(direct_result_request_seen and swot_quadrants_present and checkpoint_count == 0),
        "staged_path_obeyed": bool(checkpoint_count > 0),
        "missing_info_detected": missing_info_detected,
        "missing_info_followup_precision": bool(missing_info_detected and not first_answer_swot),
    }

    output_structure_signals = {
        "swot_quadrants_present": swot_quadrants_present,
        "strategy_section_present": strategy_section_present,
        "binary_push_detected": _contains_any(all_assistant_text.lower(), BINARY_PUSH_KEYWORDS),
        "overlong_first_answer": len(first_answer_text) > 1200,
        "premature_full_answer": bool(
            not direct_result_request_seen and _has_swot_structure(first_answer_text) and checkpoint_count == 0 and len(turns) > 1
        ),
    }

    noise_before_first_answer = any(
        int(item["turn_index"]) <= int(first_answer_turn_index or 0) for item in noise_events
    )
    command_like_events = [
        item
        for item in normalized_event_items
        if item["event_type"] in {"command_started", "command_completed", "skill_proxy_read", "skill_canonical_read", "skill_meta_read"}
    ]
    host_interference_signals = {
        "plugin_sync_noise_present": any(item["event_type"] == "plugin_interference" for item in noise_events),
        "cloudflare_or_html_challenge_present": any(item["event_type"] == "network_interference" for item in noise_events),
        "constrained_language_warning_present": any(
            "constrainedlanguage" in item["evidence_text"].lower() for item in noise_events
        ),
        "stderr_noise_ratio": round(len(noise_events) / max(len(command_like_events) + len(noise_events), 1), 4),
        "external_noise_before_first_answer": bool(noise_before_first_answer),
    }

    snippets = _top_evidence_snippets(normalized_events)
    packet_seed = {
        "trigger": {
            "proxy_skill_read": trigger_signals["proxy_skill_read"],
            "canonical_skill_read": trigger_signals["canonical_skill_read"],
            "skill_read_before_first_answer": trigger_signals["skill_read_before_first_answer"],
            "first_answer_turn_index": trigger_signals["first_answer_turn_index"],
            "first_skill_read_turn_index": trigger_signals["first_skill_read_turn_index"],
        },
        "protocol": {
            "direct_result_request_seen": protocol_signals["direct_result_request_seen"],
            "followup_question_count": protocol_signals["followup_question_count"],
            "checkpoint_count": protocol_signals["checkpoint_count"],
            "continue_branch_seen": protocol_signals["continue_branch_seen"],
            "revise_branch_seen": protocol_signals["revise_branch_seen"],
            "missing_info_detected": protocol_signals["missing_info_detected"],
        },
        "output": {
            "swot_quadrants_present": output_structure_signals["swot_quadrants_present"],
            "strategy_section_present": output_structure_signals["strategy_section_present"],
            "premature_full_answer": output_structure_signals["premature_full_answer"],
        },
        "noise": {
            "plugin_sync_noise_present": host_interference_signals["plugin_sync_noise_present"],
            "cloudflare_or_html_challenge_present": host_interference_signals["cloudflare_or_html_challenge_present"],
            "external_noise_before_first_answer": host_interference_signals["external_noise_before_first_answer"],
        },
        "evidence_snippets": snippets,
    }
    analysis_packet, analysis_packet_chars = _fit_packet(packet_seed)

    return {
        "metadata": {
            "thread_id": transcript.get("thread_id"),
            "package_name": transcript.get("package_name", ""),
            "turn_count": len(turns),
        },
        "trigger_signals": trigger_signals,
        "routing_signals": routing_signals,
        "protocol_signals": protocol_signals,
        "output_structure_signals": output_structure_signals,
        "host_interference_signals": host_interference_signals,
        "evidence_snippets": snippets,
        "prompt_budget": {
            **PROMPT_BUDGET,
            "analysis_packet_chars": analysis_packet_chars,
            "within_budget": analysis_packet_chars <= MAX_HOST_PACKET_CHARS,
        },
        "analysis_packet": analysis_packet,
    }


__all__ = ["extract_host_signals"]
