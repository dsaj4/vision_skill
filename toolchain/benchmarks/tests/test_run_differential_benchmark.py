from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.run_differential_benchmark import run_differential_benchmark


def write_run(run_dir: Path, response: str, pass_rate: float, total_tokens: int, duration_seconds: float) -> None:
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
    (run_dir / "grading.json").write_text(
        json.dumps(
            {
                "summary": {
                    "pass_rate": pass_rate,
                    "passed": 3 if pass_rate == 1.0 else 2,
                    "failed": 0 if pass_rate == 1.0 else 1,
                    "total": 3,
                },
                "execution_metrics": {
                    "response_character_count": len(response),
                    "errors_encountered": 0,
                },
                "output_file": str(run_dir / "outputs" / "final_response.md"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "timing.json").write_text(
        json.dumps(
            {
                "total_duration_seconds": duration_seconds,
                "total_tokens": total_tokens,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot",
                "prompt": "Help me decide whether to launch a product.",
                "expected_output": "A full SWOT style answer with judgment support.",
                "assertions": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_run(
        eval_dir / "with_skill" / "run-1",
        "## Strengths\n- clear guidance\n## Tradeoffs\n- explicit tradeoffs",
        pass_rate=1.0,
        total_tokens=1400,
        duration_seconds=12.0,
    )
    write_run(
        eval_dir / "without_skill" / "run-1",
        "A decent answer that is less structured.",
        pass_rate=0.6667,
        total_tokens=900,
        duration_seconds=9.0,
    )
    return iteration_dir


def make_sender() -> callable:
    call_count = {"value": 0}

    def sender(payload: dict) -> dict:
        call_count["value"] += 1
        winner = "A" if call_count["value"] == 1 else "B"
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "winner": winner,
                                "margin": 0.6 if winner == "A" else 0.4,
                                "confidence": 0.8,
                                "reasoning_summary": "One answer is clearly more helpful.",
                                "rubric_winner_by_dimension": {
                                    "Thinking Support": winner,
                                    "Tradeoff Quality": winner,
                                    "Actionability": winner,
                                    "Judgment Preservation": "tie",
                                    "Boundary Safety": "tie",
                                },
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 180, "total_tokens": 300},
        }

    return sender


def test_run_differential_benchmark_writes_parallel_level3_artifacts(tmp_path: Path) -> None:
    iteration_dir = write_iteration(tmp_path / "differential-benchmark")

    result = run_differential_benchmark(
        iteration_dir,
        skill_name="SWOT Analysis",
        skill_path="/tmp/swot",
        sender=make_sender(),
        judge_model="kimi-for-coding",
    )

    assert (iteration_dir / "pairwise-judgment.json").exists()
    assert (iteration_dir / "pairwise-judgment-reversed.json").exists()
    assert (iteration_dir / "pairwise-consensus.json").exists()
    assert (iteration_dir / "differential-benchmark.json").exists()
    assert (iteration_dir / "differential-benchmark.md").exists()
    assert result["differential_benchmark"]["summary"]["win_rate"] == 1.0
    assert result["differential_benchmark"]["summary"]["tie_rate"] == 0.0
    assert result["differential_benchmark"]["summary"]["judge_disagreement_rate"] == 0.0


def test_run_differential_benchmark_defaults_to_single_pass_judging(tmp_path: Path) -> None:
    iteration_dir = write_iteration(tmp_path / "single-pass")
    calls = {"count": 0}

    def sender(payload: dict) -> dict:
        calls["count"] += 1
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "winner": "A",
                                "margin": 0.5,
                                "confidence": 0.8,
                                "reasoning_summary": "A is more useful.",
                                "rubric_winner_by_dimension": {
                                    "Thinking Support": "A",
                                    "Tradeoff Quality": "A",
                                    "Actionability": "A",
                                    "Judgment Preservation": "tie",
                                    "Boundary Safety": "tie",
                                },
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    result = run_differential_benchmark(iteration_dir, sender=sender)

    reversed_artifact = json.loads((iteration_dir / "pairwise-judgment-reversed.json").read_text(encoding="utf-8"))
    assert calls["count"] == 1
    assert result["differential_benchmark"]["metadata"]["judge_strategy"] == "single"
    assert result["consensus_pairs"][0]["evidence"]["judge_strategy"] == "single"
    assert reversed_artifact["judgments"] == []


def test_run_differential_benchmark_balanced_judging_uses_reversed_pass(tmp_path: Path) -> None:
    iteration_dir = write_iteration(tmp_path / "balanced")
    calls = {"count": 0}

    def sender(payload: dict) -> dict:
        calls["count"] += 1
        winner = "A" if calls["count"] == 1 else "B"
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "winner": winner,
                                "margin": 0.5,
                                "confidence": 0.8,
                                "reasoning_summary": "One candidate is more useful.",
                                "rubric_winner_by_dimension": {
                                    "Thinking Support": winner,
                                    "Tradeoff Quality": winner,
                                    "Actionability": winner,
                                    "Judgment Preservation": "tie",
                                    "Boundary Safety": "tie",
                                },
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    result = run_differential_benchmark(iteration_dir, sender=sender, judge_strategy="balanced")

    reversed_artifact = json.loads((iteration_dir / "pairwise-judgment-reversed.json").read_text(encoding="utf-8"))
    assert calls["count"] == 2
    assert result["differential_benchmark"]["metadata"]["judge_strategy"] == "balanced"
    assert len(reversed_artifact["judgments"]) == 1
