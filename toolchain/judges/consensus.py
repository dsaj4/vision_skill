from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def build_pairwise_consensus(
    forward: dict[str, Any],
    reversed_judgment: dict[str, Any],
    *,
    tiebreak: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forward_winner = forward["judgment"]["normalized_winner"]
    reversed_winner = reversed_judgment["judgment"]["normalized_winner"]
    comparable = forward["gate_check"]["comparable"] and reversed_judgment["gate_check"]["comparable"]
    disagreement = comparable and forward_winner != reversed_winner

    final_winner = "not_comparable"
    tiebreak_used = False
    margins = [
        float(forward["judgment"].get("margin", 0.0) or 0.0),
        float(reversed_judgment["judgment"].get("margin", 0.0) or 0.0),
    ]

    if not comparable or forward_winner == "not_comparable" or reversed_winner == "not_comparable":
        final_winner = "not_comparable"
    elif not disagreement:
        final_winner = forward_winner
    elif tiebreak is not None:
        tiebreak_used = True
        final_winner = tiebreak["judgment"]["normalized_winner"]
        margins.append(float(tiebreak["judgment"].get("margin", 0.0) or 0.0))
    else:
        final_winner = "tie"

    candidate_a = forward.get("pair", {}).get("candidate_a", {})
    candidate_b = forward.get("pair", {}).get("candidate_b", {})
    with_skill_run_dir = candidate_a.get("run_dir", "") if candidate_a.get("configuration") == "with_skill" else candidate_b.get("run_dir", "")
    without_skill_run_dir = candidate_a.get("run_dir", "") if candidate_a.get("configuration") == "without_skill" else candidate_b.get("run_dir", "")

    return {
        "metadata": {
            "eval_id": forward["metadata"]["eval_id"],
            "eval_name": forward["metadata"]["eval_name"],
            "run_number": forward["metadata"]["run_number"],
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "eval_id": forward["metadata"]["eval_id"],
        "eval_name": forward["metadata"]["eval_name"],
        "run_number": forward["metadata"]["run_number"],
        "forward_winner": forward_winner,
        "reversed_winner": reversed_winner,
        "final_winner": final_winner,
        "judge_disagreement": disagreement,
        "tiebreak_used": tiebreak_used,
        "avg_margin": _mean(margins if comparable else []),
        "cost": forward.get("cost", {}),
        "with_skill_run_dir": str(with_skill_run_dir),
        "without_skill_run_dir": str(without_skill_run_dir),
        "evidence": {
            "forward_orientation": forward["metadata"]["orientation"],
            "reversed_orientation": reversed_judgment["metadata"]["orientation"],
            "tiebreak_orientation": tiebreak["metadata"]["orientation"] if tiebreak else "",
        },
    }
