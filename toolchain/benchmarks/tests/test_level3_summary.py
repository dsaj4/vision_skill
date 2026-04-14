from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.level3_summary import generate_level3_summary, write_level3_summary_artifacts


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "benchmark.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "skill_name": "SWOT Analysis",
                    "skill_path": "/tmp/swot",
                },
                "run_summary": {
                    "with_skill": {
                        "pass_rate": {"mean": 0.6667},
                        "time_seconds": {"mean": 12.0},
                        "tokens": {"mean": 1200.0},
                    },
                    "without_skill": {
                        "pass_rate": {"mean": 0.6667},
                        "time_seconds": {"mean": 8.0},
                        "tokens": {"mean": 800.0},
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (iteration_dir / "differential-benchmark.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "skill_name": "SWOT Analysis",
                    "skill_path": "/tmp/swot",
                },
                "summary": {
                    "win_rate": 0.5,
                    "tie_rate": 0.0,
                    "avg_margin": 0.1,
                    "judge_disagreement_rate": 0.0,
                    "cost_adjusted_value": -0.05,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (iteration_dir / "pairwise-consensus.json").write_text(
        json.dumps(
            {
                "metadata": {"generated_at": "2026-04-14T00:00:00Z"},
                "pairs": [
                    {
                        "eval_id": 101,
                        "eval_name": "ai-swot",
                        "run_number": 1,
                        "final_winner": "with_skill",
                        "avg_margin": 0.75,
                        "judge_disagreement": False,
                        "with_skill_run_dir": "E:/tmp/with_skill/run-1",
                        "without_skill_run_dir": "E:/tmp/without_skill/run-1",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return iteration_dir


def test_generate_level3_summary_normalizes_gate_and_differential_artifacts(tmp_path: Path) -> None:
    iteration_dir = write_iteration(tmp_path)

    summary = generate_level3_summary(iteration_dir)
    write_level3_summary_artifacts(iteration_dir, summary)

    assert summary["primary_mode"] == "differential"
    assert summary["pairwise_summary"]["win_rate"] == 0.5
    assert summary["gate_summary"]["with_skill"]["pass_rate"]["mean"] == 0.6667
    assert summary["per_eval"][0]["with_skill_run_dir"].endswith("run-1")
    assert (iteration_dir / "level3-summary.json").exists()
    assert (iteration_dir / "level3-summary.md").exists()


def test_generate_level3_summary_requires_differential_artifact(tmp_path: Path) -> None:
    iteration_dir = tmp_path / "iteration-1"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "benchmark.json").write_text("{}", encoding="utf-8")

    try:
        generate_level3_summary(iteration_dir)
    except FileNotFoundError as exc:
        assert "differential-benchmark.json" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError when differential-benchmark.json is missing.")
