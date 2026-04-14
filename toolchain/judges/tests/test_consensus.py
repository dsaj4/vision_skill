from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.judges.consensus import build_pairwise_consensus


def make_judgment(normalized_winner: str, margin: float, orientation: str = "forward") -> dict:
    return {
        "metadata": {
            "eval_id": 1,
            "eval_name": "swot",
            "run_number": 1,
            "orientation": orientation,
            "judge_model": "qwen-judge-test",
        },
        "pair": {
            "candidate_a": {"configuration": "with_skill" if orientation == "forward" else "without_skill"},
            "candidate_b": {"configuration": "without_skill" if orientation == "forward" else "with_skill"},
        },
        "gate_check": {"comparable": True, "reasons": []},
        "judgment": {
            "winner": "A",
            "normalized_winner": normalized_winner,
            "margin": margin,
            "confidence": 0.8,
            "reasoning_summary": "summary",
            "rubric_winner_by_dimension": {},
        },
        "cost": {
            "with_skill": {"time_seconds": 12.0, "tokens": 1200},
            "without_skill": {"time_seconds": 9.0, "tokens": 900},
        },
    }


def test_build_pairwise_consensus_agrees_when_forward_and_reverse_match() -> None:
    forward = make_judgment("with_skill", 0.6, orientation="forward")
    reversed_judgment = make_judgment("with_skill", 0.4, orientation="reversed")

    result = build_pairwise_consensus(forward, reversed_judgment)

    assert result["final_winner"] == "with_skill"
    assert result["judge_disagreement"] is False
    assert result["tiebreak_used"] is False
    assert result["avg_margin"] == 0.5


def test_build_pairwise_consensus_uses_tiebreak_when_needed() -> None:
    forward = make_judgment("with_skill", 0.6, orientation="forward")
    reversed_judgment = make_judgment("without_skill", 0.6, orientation="reversed")
    tiebreak = make_judgment("tie", 0.0, orientation="tiebreak")

    result = build_pairwise_consensus(forward, reversed_judgment, tiebreak=tiebreak)

    assert result["judge_disagreement"] is True
    assert result["tiebreak_used"] is True
    assert result["final_winner"] == "tie"
