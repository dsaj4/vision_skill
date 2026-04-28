from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.run_benchmark import grade_iteration_runs


def write_eval_run(eval_dir: Path, configuration: str, run_number: int, response: str) -> None:
    run_dir = eval_dir / configuration / f"run-{run_number}"
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
    (run_dir / "timing.json").write_text(
        json.dumps(
            {
                "total_tokens": 1200 if configuration == "with_skill" else 800,
                "total_duration_seconds": 10.0 if configuration == "with_skill" else 8.0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_grade_iteration_runs_writes_grading_and_benchmark_artifacts(tmp_path: Path) -> None:
    iteration_dir = tmp_path / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot-direct-result"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot-direct-result",
                "prompt": "Give me a direct SWOT result.",
                "expected_output": "A complete SWOT result.",
                "assertions": [
                    {
                        "id": "all-quadrants",
                        "type": "contains_all",
                        "keywords": ["strengths", "weaknesses", "opportunities", "threats"],
                        "text": "Must include all four SWOT quadrants.",
                    },
                    {
                        "id": "strategy-guidance",
                        "type": "contains_any",
                        "keywords": ["strategy", "建议", "行动"],
                        "text": "Must include strategy guidance.",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_eval_run(
        eval_dir,
        "with_skill",
        1,
        """
## Strengths
- 用户洞察
## Weaknesses
- 预算有限
## Opportunities
- 市场存在空白
## Threats
- 竞品动作快
## Strategy
- 先验证需求再扩张
""".strip(),
    )
    write_eval_run(
        eval_dir,
        "without_skill",
        1,
        """
你可以试试看这个方向，但要注意竞争和预算。
""".strip(),
    )

    result = grade_iteration_runs(iteration_dir, skill_name="SWOT 分析", skill_path="/tmp/swot")

    assert result["benchmark"]["metadata"]["skill_name"] == "SWOT 分析"
    assert (eval_dir / "with_skill" / "run-1" / "grading.json").exists()
    assert (eval_dir / "without_skill" / "run-1" / "grading.json").exists()
    assert (iteration_dir / "benchmark.json").exists()
    assert (iteration_dir / "benchmark.md").exists()
    assert result["benchmark"]["run_summary"]["delta"]["pass_rate"].startswith("+")


def test_grade_iteration_runs_ignores_inactive_run_dirs_from_iteration_config(tmp_path: Path) -> None:
    iteration_dir = tmp_path / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot-direct-result"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "iteration_config.json").write_text(
        json.dumps({"runs_per_configuration": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot-direct-result",
                "prompt": "Give me a direct SWOT result.",
                "expected_output": "A complete SWOT result.",
                "assertions": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_eval_run(eval_dir, "with_skill", 1, "active with-skill answer")
    write_eval_run(eval_dir, "with_skill", 2, "inactive with-skill answer")
    write_eval_run(eval_dir, "without_skill", 1, "active baseline answer")
    write_eval_run(eval_dir, "without_skill", 2, "inactive baseline answer")

    result = grade_iteration_runs(iteration_dir)

    assert len(result["graded_runs"]) == 2
    assert (eval_dir / "with_skill" / "run-1" / "grading.json").exists()
    assert not (eval_dir / "with_skill" / "run-2" / "grading.json").exists()
    assert result["benchmark"]["metadata"]["runs_per_configuration"] == 1
