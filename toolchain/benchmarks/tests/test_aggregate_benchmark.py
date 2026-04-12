from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.aggregate_benchmark import generate_benchmark, generate_markdown


def write_run(run_dir: Path, pass_rate: float, passed: int, failed: int, total: int, seconds: float, tokens: int) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "grading.json").write_text(
        json.dumps(
            {
                "expectations": [
                    {"text": "Expectation", "passed": pass_rate > 0.5, "evidence": "Synthetic evidence"}
                ],
                "summary": {
                    "passed": passed,
                    "failed": failed,
                    "total": total,
                    "pass_rate": pass_rate,
                },
                "execution_metrics": {
                    "total_tool_calls": 4,
                    "errors_encountered": 0,
                },
                "timing": {
                    "total_duration_seconds": seconds,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "timing.json").write_text(
        json.dumps(
            {
                "total_tokens": tokens,
                "total_duration_seconds": seconds,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_generate_benchmark_aggregates_run_summary_and_delta(tmp_path: Path) -> None:
    iteration_dir = tmp_path / "iteration-1"
    eval_dir = iteration_dir / "eval-1-example"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "example",
                "prompt": "Example prompt",
                "assertions": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_run(eval_dir / "with_skill" / "run-1", 1.0, 3, 0, 3, 12.0, 1000)
    write_run(eval_dir / "without_skill" / "run-1", 0.33, 1, 2, 3, 8.0, 600)

    benchmark = generate_benchmark(iteration_dir, skill_name="Example Skill", skill_path="/tmp/example")

    assert benchmark["metadata"]["skill_name"] == "Example Skill"
    assert len(benchmark["runs"]) == 2
    assert benchmark["run_summary"]["with_skill"]["pass_rate"]["mean"] == 1.0
    assert benchmark["run_summary"]["without_skill"]["pass_rate"]["mean"] == 0.33
    assert benchmark["run_summary"]["delta"]["pass_rate"].startswith("+")


def test_generate_markdown_includes_summary_table(tmp_path: Path) -> None:
    iteration_dir = tmp_path / "iteration-1"
    eval_dir = iteration_dir / "eval-1-example"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "example",
                "prompt": "Example prompt",
                "assertions": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_run(eval_dir / "with_skill" / "run-1", 0.75, 3, 1, 4, 10.0, 900)
    write_run(eval_dir / "without_skill" / "run-1", 0.25, 1, 3, 4, 7.0, 500)

    benchmark = generate_benchmark(iteration_dir, skill_name="Example Skill", skill_path="/tmp/example")
    markdown = generate_markdown(benchmark)

    assert "# Skill Benchmark: Example Skill" in markdown
    assert "| Metric |" in markdown
    assert "With Skill" in markdown
