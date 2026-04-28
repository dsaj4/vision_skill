from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from toolchain.common import is_active_run_dir, load_json, write_json, write_text
from toolchain.benchmarks.aggregate_benchmark import generate_benchmark
from toolchain.judges.consensus import build_pairwise_consensus
from toolchain.judges.pairwise_judge import Sender, judge_pair
from toolchain.kimi_runtime import CommandRunner


def _collect_pairs(iteration_dir: Path) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        eval_metadata = load_json(eval_dir / "eval_metadata.json")
        with_skill_runs = {
            run_dir.name: run_dir
            for run_dir in sorted((eval_dir / "with_skill").glob("run-*"))
            if is_active_run_dir(run_dir, iteration_dir) and (run_dir / "grading.json").exists()
        }
        without_skill_runs = {
            run_dir.name: run_dir
            for run_dir in sorted((eval_dir / "without_skill").glob("run-*"))
            if is_active_run_dir(run_dir, iteration_dir) and (run_dir / "grading.json").exists()
        }

        for run_name in sorted(set(with_skill_runs.keys()) & set(without_skill_runs.keys())):
            pairs.append(
                {
                    "eval_id": eval_metadata["eval_id"],
                    "eval_name": eval_metadata.get("eval_name", eval_dir.name),
                    "prompt": eval_metadata.get("prompt", ""),
                    "run_number": int(run_name.split("-")[1]),
                    "with_skill_run_dir": with_skill_runs[run_name],
                    "without_skill_run_dir": without_skill_runs[run_name],
                }
            )
    return pairs


def _signed_margin(pair_result: dict[str, Any]) -> float:
    winner = pair_result.get("final_winner", "tie")
    margin = float(pair_result.get("avg_margin", 0.0) or 0.0)
    if winner == "with_skill":
        return margin
    if winner == "without_skill":
        return -margin
    return 0.0


def _cost_adjusted_value(avg_margin: float, with_skill: dict[str, Any], without_skill: dict[str, Any]) -> float:
    with_tokens = float(with_skill.get("tokens", {}).get("mean", 0.0) or 0.0)
    without_tokens = float(without_skill.get("tokens", {}).get("mean", 0.0) or 0.0)
    with_time = float(with_skill.get("time_seconds", {}).get("mean", 0.0) or 0.0)
    without_time = float(without_skill.get("time_seconds", {}).get("mean", 0.0) or 0.0)

    token_penalty = max(with_tokens - without_tokens, 0.0) / max(without_tokens, 1.0) * 0.15
    time_penalty = max(with_time - without_time, 0.0) / max(without_time, 1.0) * 0.10
    return round(avg_margin - token_penalty - time_penalty, 4)


def _build_single_pass_consensus(forward: dict[str, Any]) -> dict[str, Any]:
    candidate_a = forward.get("pair", {}).get("candidate_a", {})
    candidate_b = forward.get("pair", {}).get("candidate_b", {})
    with_skill_run_dir = candidate_a.get("run_dir", "") if candidate_a.get("configuration") == "with_skill" else candidate_b.get("run_dir", "")
    without_skill_run_dir = candidate_a.get("run_dir", "") if candidate_a.get("configuration") == "without_skill" else candidate_b.get("run_dir", "")
    comparable = bool(forward.get("gate_check", {}).get("comparable", False))
    forward_winner = forward["judgment"]["normalized_winner"]

    return {
        "metadata": {
            "eval_id": forward["metadata"]["eval_id"],
            "eval_name": forward["metadata"]["eval_name"],
            "run_number": forward["metadata"]["run_number"],
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "judge_strategy": "single",
        },
        "eval_id": forward["metadata"]["eval_id"],
        "eval_name": forward["metadata"]["eval_name"],
        "run_number": forward["metadata"]["run_number"],
        "forward_winner": forward_winner,
        "reversed_winner": "",
        "final_winner": forward_winner if comparable else "not_comparable",
        "judge_disagreement": False,
        "tiebreak_used": False,
        "avg_margin": float(forward["judgment"].get("margin", 0.0) or 0.0) if comparable else 0.0,
        "cost": forward.get("cost", {}),
        "with_skill_run_dir": str(with_skill_run_dir),
        "without_skill_run_dir": str(without_skill_run_dir),
        "evidence": {
            "forward_orientation": forward["metadata"]["orientation"],
            "reversed_orientation": "",
            "tiebreak_orientation": "",
            "judge_strategy": "single",
        },
    }


def _build_summary(consensus_pairs: list[dict[str, Any]], supporting_benchmark: dict[str, Any]) -> dict[str, Any]:
    comparable = [pair for pair in consensus_pairs if pair["final_winner"] != "not_comparable"]
    total = len(comparable)
    with_skill_wins = sum(1 for pair in comparable if pair["final_winner"] == "with_skill")
    without_skill_wins = sum(1 for pair in comparable if pair["final_winner"] == "without_skill")
    ties = sum(1 for pair in comparable if pair["final_winner"] == "tie")
    disagreement = sum(1 for pair in comparable if pair["judge_disagreement"])
    avg_margin = round(sum(_signed_margin(pair) for pair in comparable) / total, 4) if total else 0.0

    supporting = supporting_benchmark.get("run_summary", {})
    with_skill_support = supporting.get("with_skill", {})
    without_skill_support = supporting.get("without_skill", {})

    return {
        "pair_count": len(consensus_pairs),
        "comparable_pair_count": total,
        "not_comparable_count": len(consensus_pairs) - total,
        "win_rate": round(with_skill_wins / total, 4) if total else 0.0,
        "loss_rate": round(without_skill_wins / total, 4) if total else 0.0,
        "tie_rate": round(ties / total, 4) if total else 0.0,
        "avg_margin": avg_margin,
        "judge_disagreement_rate": round(disagreement / total, 4) if total else 0.0,
        "cost_adjusted_value": _cost_adjusted_value(avg_margin, with_skill_support, without_skill_support),
        "supporting_metrics": {
            "with_skill": with_skill_support,
            "without_skill": without_skill_support,
        },
    }


def _generate_markdown(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]
    lines = [
        "# Differential Benchmark",
        "",
        f"**Generated At**: {artifact['metadata']['generated_at']}",
        "",
        "## Summary",
        "",
        f"- Judge strategy: {artifact['metadata'].get('judge_strategy', 'unknown')}",
        f"- Pair count: {summary['pair_count']}",
        f"- Comparable pairs: {summary['comparable_pair_count']}",
        f"- Win rate: {summary['win_rate']:.4f}",
        f"- Tie rate: {summary['tie_rate']:.4f}",
        f"- Avg margin: {summary['avg_margin']:.4f}",
        f"- Judge disagreement rate: {summary['judge_disagreement_rate']:.4f}",
        f"- Cost-adjusted value: {summary['cost_adjusted_value']:.4f}",
        "",
        "## Pair Results",
        "",
    ]
    for pair in artifact["pairs"]:
        lines.append(
            f"- Eval {pair['eval_id']} / run-{pair['run_number']}: winner={pair['final_winner']}, "
            f"margin={pair['avg_margin']:.4f}, disagreement={pair['judge_disagreement']}"
        )
    return "\n".join(lines).strip() + "\n"


def run_differential_benchmark(
    iteration_dir: str | Path,
    *,
    skill_name: str = "",
    skill_path: str = "",
    sender: Sender | None = None,
    command_runner: CommandRunner | None = None,
    judge_model: str | None = None,
    timeout_seconds: int | None = None,
    allow_tiebreak: bool = True,
    judge_strategy: str = "single",
) -> dict[str, Any]:
    iteration_path = Path(iteration_dir)
    if judge_strategy not in {"single", "balanced"}:
        raise ValueError("judge_strategy must be either 'single' or 'balanced'.")
    pairs = _collect_pairs(iteration_path)
    forward_judgments: list[dict[str, Any]] = []
    reversed_judgments: list[dict[str, Any]] = []
    consensus_pairs: list[dict[str, Any]] = []

    for pair in pairs:
        forward = judge_pair(
            eval_id=pair["eval_id"],
            eval_name=pair["eval_name"],
            prompt=pair["prompt"],
            run_number=pair["run_number"],
            with_skill_run_dir=pair["with_skill_run_dir"],
            without_skill_run_dir=pair["without_skill_run_dir"],
            orientation="forward",
            sender=sender,
            command_runner=command_runner,
            judge_model=judge_model,
            timeout_seconds=timeout_seconds,
        )
        if judge_strategy == "single":
            consensus = _build_single_pass_consensus(forward)
        else:
            reversed_judgment = judge_pair(
                eval_id=pair["eval_id"],
                eval_name=pair["eval_name"],
                prompt=pair["prompt"],
                run_number=pair["run_number"],
                with_skill_run_dir=pair["with_skill_run_dir"],
                without_skill_run_dir=pair["without_skill_run_dir"],
                orientation="reversed",
                sender=sender,
                command_runner=command_runner,
                judge_model=judge_model,
                timeout_seconds=timeout_seconds,
            )
            tiebreak = None
            if allow_tiebreak and forward["judgment"]["normalized_winner"] != reversed_judgment["judgment"]["normalized_winner"]:
                tiebreak = judge_pair(
                    eval_id=pair["eval_id"],
                    eval_name=pair["eval_name"],
                    prompt=pair["prompt"],
                    run_number=pair["run_number"],
                    with_skill_run_dir=pair["with_skill_run_dir"],
                    without_skill_run_dir=pair["without_skill_run_dir"],
                    orientation="tiebreak",
                    sender=sender,
                    command_runner=command_runner,
                    judge_model=judge_model,
                    timeout_seconds=timeout_seconds,
                )
            consensus = build_pairwise_consensus(forward, reversed_judgment, tiebreak=tiebreak)
            reversed_judgments.append(reversed_judgment)

        forward_judgments.append(forward)
        consensus_pairs.append(consensus)

    supporting_benchmark = generate_benchmark(iteration_path, skill_name=skill_name, skill_path=skill_path)
    differential_benchmark = {
        "metadata": {
            "skill_name": skill_name or supporting_benchmark.get("metadata", {}).get("skill_name", "<skill-name>"),
            "skill_path": skill_path or supporting_benchmark.get("metadata", {}).get("skill_path", "<skill-path>"),
            "judge_model": judge_model or "",
            "judge_strategy": judge_strategy,
            "allow_tiebreak": allow_tiebreak if judge_strategy == "balanced" else False,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "eval_ids": sorted({pair["metadata"]["eval_id"] for pair in consensus_pairs}),
        },
        "pairs": consensus_pairs,
        "summary": _build_summary(consensus_pairs, supporting_benchmark),
    }

    write_json(
        iteration_path / "pairwise-judgment.json",
        {
            "metadata": {
                "generated_at": differential_benchmark["metadata"]["generated_at"],
                "judge_strategy": judge_strategy,
            },
            "judgments": forward_judgments,
        },
    )
    write_json(
        iteration_path / "pairwise-judgment-reversed.json",
        {
            "metadata": {
                "generated_at": differential_benchmark["metadata"]["generated_at"],
                "judge_strategy": judge_strategy,
            },
            "judgments": reversed_judgments,
        },
    )
    write_json(
        iteration_path / "pairwise-consensus.json",
        {
            "metadata": {
                "generated_at": differential_benchmark["metadata"]["generated_at"],
                "judge_strategy": judge_strategy,
            },
            "pairs": consensus_pairs,
        },
    )
    write_json(iteration_path / "differential-benchmark.json", differential_benchmark)
    write_text(iteration_path / "differential-benchmark.md", _generate_markdown(differential_benchmark))

    return {
        "forward_judgments": forward_judgments,
        "reversed_judgments": reversed_judgments,
        "consensus_pairs": consensus_pairs,
        "differential_benchmark": differential_benchmark,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pairwise differential benchmark artifacts in parallel with the current Level 3 path.")
    parser.add_argument("--iteration-dir", required=True, help="Path to the iteration directory.")
    parser.add_argument("--skill-name", default="", help="Optional skill name for benchmark metadata.")
    parser.add_argument("--skill-path", default="", help="Optional skill path for benchmark metadata.")
    parser.add_argument("--judge-model", default=None, help="Optional judge model override.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional timeout override.")
    parser.add_argument(
        "--no-tiebreak",
        action="store_true",
        help="Disable the third tiebreak pass when balanced judging is enabled and forward/reversed judgments disagree.",
    )
    parser.add_argument(
        "--balanced-judging",
        action="store_true",
        help="Use the slower forward + reversed judging strategy. The default is single-pass judging.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_differential_benchmark(
        args.iteration_dir,
        skill_name=args.skill_name,
        skill_path=args.skill_path,
        judge_model=args.judge_model,
        timeout_seconds=args.timeout_seconds,
        allow_tiebreak=not args.no_tiebreak,
        judge_strategy="balanced" if args.balanced_judging else "single",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
