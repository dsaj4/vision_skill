from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.agent_hosts.event_normalizer import normalize_host_transcript
from toolchain.agent_hosts.protocol_classifier import classify_protocol_path
from toolchain.agent_hosts.signal_extractor import extract_host_signals


def _make_transcript(*, user_turns: list[str], assistant_turns: list[str], include_reads: bool = True) -> dict:
    turns = []
    for index, user_text in enumerate(user_turns, start=1):
        assistant_text = assistant_turns[index - 1]
        events = []
        if include_reads and index == 1:
            events = [
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "Get-Content 'E:/repo/session/.codex/skills/swot-analysis/SKILL.md'",
                        "aggregated_output": "proxy skill text",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "Get-Content 'E:/repo/packages/swot-analysis/SKILL.md'",
                        "aggregated_output": "canonical skill text",
                    },
                },
            ]
        turns.append(
            {
                "turn_index": index,
                "user_text": user_text,
                "assistant_text": assistant_text,
                "events": events,
                "warnings": [],
                "stderr": "",
            }
        )
    return {
        "thread_id": "thread-1",
        "package_name": "swot-analysis",
        "package_dir": "E:/repo/packages/swot-analysis",
        "proxy_skill_path": "E:/repo/session/.codex/skills/swot-analysis/SKILL.md",
        "canonical_skill_path": "E:/repo/packages/swot-analysis/SKILL.md",
        "turns": turns,
        "stderr": [],
    }


def test_signal_report_prioritizes_evidence_and_respects_budget() -> None:
    transcript = _make_transcript(
        user_turns=["Give me the SWOT directly and do not confirm."],
        assistant_turns=[
            "## Strengths\n- traction\n## Weaknesses\n- budget\n## Opportunities\n- demand\n## Threats\n- competition\n## Strategy\n- validate first"
        ],
    )
    normalized = normalize_host_transcript(transcript)
    signals = extract_host_signals(transcript, normalized)

    assert signals["trigger_signals"]["proxy_skill_read"] is True
    assert signals["trigger_signals"]["canonical_skill_read"] is True
    assert signals["trigger_signals"]["skill_read_before_first_answer"] is True
    assert signals["prompt_budget"]["within_budget"] is True
    assert len(signals["evidence_snippets"]) <= 6


def test_protocol_classifier_handles_key_paths() -> None:
    ask_followup = {
        "protocol_signals": {
            "direct_result_request_seen": False,
            "missing_info_detected": True,
            "followup_question_count": 2,
            "checkpoint_count": 0,
            "continue_branch_seen": False,
            "revise_branch_seen": False,
            "direct_result_obeyed": False,
        },
        "output_structure_signals": {"swot_quadrants_present": False, "premature_full_answer": False},
    }
    premature = {
        "protocol_signals": {
            "direct_result_request_seen": False,
            "missing_info_detected": True,
            "followup_question_count": 0,
            "checkpoint_count": 0,
            "continue_branch_seen": False,
            "revise_branch_seen": False,
            "direct_result_obeyed": False,
        },
        "output_structure_signals": {"swot_quadrants_present": True, "premature_full_answer": True},
    }
    direct = {
        "protocol_signals": {
            "direct_result_request_seen": True,
            "missing_info_detected": False,
            "followup_question_count": 0,
            "checkpoint_count": 0,
            "continue_branch_seen": False,
            "revise_branch_seen": False,
            "direct_result_obeyed": True,
        },
        "output_structure_signals": {"swot_quadrants_present": True, "premature_full_answer": False},
    }
    violated = {
        "protocol_signals": {
            "direct_result_request_seen": True,
            "missing_info_detected": False,
            "followup_question_count": 0,
            "checkpoint_count": 1,
            "continue_branch_seen": False,
            "revise_branch_seen": False,
            "direct_result_obeyed": False,
        },
        "output_structure_signals": {"swot_quadrants_present": True, "premature_full_answer": False},
    }
    continue_loop = {
        "protocol_signals": {
            "direct_result_request_seen": False,
            "missing_info_detected": False,
            "followup_question_count": 0,
            "checkpoint_count": 1,
            "continue_branch_seen": True,
            "revise_branch_seen": False,
            "direct_result_obeyed": False,
        },
        "output_structure_signals": {"swot_quadrants_present": False, "premature_full_answer": False},
    }
    revise_loop = {
        "protocol_signals": {
            "direct_result_request_seen": False,
            "missing_info_detected": False,
            "followup_question_count": 0,
            "checkpoint_count": 1,
            "continue_branch_seen": False,
            "revise_branch_seen": True,
            "direct_result_obeyed": False,
        },
        "output_structure_signals": {"swot_quadrants_present": False, "premature_full_answer": False},
    }

    assert classify_protocol_path(ask_followup)["observed_protocol_path"] == "missing-info -> ask-followup"
    assert classify_protocol_path(premature)["observed_protocol_path"] == "missing-info -> premature-full-answer"
    assert classify_protocol_path(direct)["observed_protocol_path"] == "direct-result -> no-checkpoint"
    assert classify_protocol_path(violated)["observed_protocol_path"] == "direct-result -> violated-by-checkpoint"
    assert classify_protocol_path(continue_loop)["observed_protocol_path"] == "staged -> continue-loop"
    assert classify_protocol_path(revise_loop)["observed_protocol_path"] == "staged -> revise-loop"
