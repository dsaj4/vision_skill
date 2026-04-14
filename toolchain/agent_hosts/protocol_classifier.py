from __future__ import annotations

from typing import Any


ALLOWED_PROTOCOL_PATHS = {
    "missing-info -> ask-followup",
    "missing-info -> premature-full-answer",
    "direct-result -> no-checkpoint",
    "direct-result -> violated-by-checkpoint",
    "staged -> pause-after-step1",
    "staged -> skipped-checkpoint",
    "staged -> continue-loop",
    "staged -> revise-loop",
    "unknown",
}


def classify_protocol_path(signal_report: dict[str, Any]) -> dict[str, Any]:
    protocol = signal_report.get("protocol_signals", {})
    output = signal_report.get("output_structure_signals", {})

    supporting: list[str] = []
    blocking: list[str] = []
    path = "unknown"

    if protocol.get("direct_result_request_seen"):
        supporting.append("direct_result_request_seen")
        if int(protocol.get("checkpoint_count", 0) or 0) > 0:
            supporting.append("checkpoint_count")
            path = "direct-result -> violated-by-checkpoint"
        elif output.get("swot_quadrants_present") or protocol.get("direct_result_obeyed"):
            supporting.extend(["swot_quadrants_present", "no_checkpoint"])
            path = "direct-result -> no-checkpoint"
        else:
            blocking.append("missing_direct_result_evidence")

    elif protocol.get("missing_info_detected"):
        supporting.append("missing_info_detected")
        if output.get("premature_full_answer"):
            supporting.append("premature_full_answer")
            path = "missing-info -> premature-full-answer"
        elif int(protocol.get("followup_question_count", 0) or 0) > 0 or protocol.get("missing_info_followup_precision"):
            if int(protocol.get("followup_question_count", 0) or 0) > 0:
                supporting.append("followup_question_count")
            if protocol.get("missing_info_followup_precision"):
                supporting.append("missing_info_followup_precision")
            path = "missing-info -> ask-followup"
        elif not output.get("swot_quadrants_present"):
            supporting.append("no_immediate_full_answer")
            path = "missing-info -> ask-followup"
        else:
            blocking.append("missing_followup_evidence")

    elif int(protocol.get("checkpoint_count", 0) or 0) > 0:
        supporting.append("checkpoint_count")
        if protocol.get("revise_branch_seen"):
            supporting.append("revise_branch_seen")
            path = "staged -> revise-loop"
        elif protocol.get("continue_branch_seen"):
            supporting.append("continue_branch_seen")
            path = "staged -> continue-loop"
        else:
            path = "staged -> pause-after-step1"

    elif protocol.get("revise_branch_seen") or protocol.get("continue_branch_seen"):
        supporting.append("branch_seen_without_checkpoint")
        if protocol.get("revise_branch_seen"):
            supporting.append("revise_branch_seen")
        if protocol.get("continue_branch_seen"):
            supporting.append("continue_branch_seen")
        path = "staged -> skipped-checkpoint"

    confidence = _path_confidence(path, supporting=supporting, blocking=blocking)
    if confidence < 0.2:
        path = "unknown"

    if path not in ALLOWED_PROTOCOL_PATHS:
        path = "unknown"

    return {
        "observed_protocol_path": path,
        "path_confidence": confidence,
        "supporting_signals": supporting,
        "blocking_signals": blocking,
    }


def _path_confidence(path: str, *, supporting: list[str], blocking: list[str]) -> float:
    if path == "unknown":
        return 0.0
    score = 0.35 + min(len(supporting), 4) * 0.15 - min(len(blocking), 2) * 0.1
    if "premature-full-answer" in path or "violated-by-checkpoint" in path:
        score += 0.1
    return round(max(0.0, min(score, 1.0)), 4)


__all__ = ["ALLOWED_PROTOCOL_PATHS", "classify_protocol_path"]
