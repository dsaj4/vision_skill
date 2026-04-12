from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.graders.capability_grader import grade_run


def write_run_fixture(base: Path, assertions: list[object], response: str) -> Path:
    run_dir = base / "with_skill" / "run-1"
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (run_dir.parent.parent / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot-direct-result",
                "prompt": "Please give me a direct SWOT result.",
                "expected_output": "A complete SWOT result.",
                "assertions": assertions,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (outputs_dir / "final_response.md").write_text(response, encoding="utf-8")
    return run_dir


def test_grade_run_supports_string_expectations_with_swot_heuristics(tmp_path: Path) -> None:
    run_dir = write_run_fixture(
        tmp_path,
        assertions=[
            "The output includes strengths, weaknesses, opportunities, and threats.",
            "The output respects the user's direct-result request.",
            "The output concludes with actionable strategy suggestions.",
        ],
        response="""
# SWOT 结果

## Strengths
- 有校园访谈经验

## Weaknesses
- 预算有限

## Opportunities
- 目标用户集中

## Threats
- 竞品进入较快

## Strategy Suggestions
- 先做最小可行版本验证需求。
""".strip(),
    )

    grading = grade_run(run_dir)

    assert grading["summary"]["total"] == 3
    assert grading["summary"]["passed"] == 3
    assert grading["summary"]["pass_rate"] == 1.0
    assert (run_dir / "grading.json").exists()
    assert (run_dir / "metrics.json").exists()


def test_grade_run_supports_structured_assertions(tmp_path: Path) -> None:
    run_dir = write_run_fixture(
        tmp_path,
        assertions=[
            {
                "id": "all-quadrants",
                "type": "contains_all",
                "keywords": ["strengths", "weaknesses", "opportunities", "threats"],
                "text": "Must include all four SWOT quadrants.",
            },
            {
                "id": "no-pause-branch",
                "type": "contains_none",
                "keywords": ['回复"继续"', '回复"不对"', '回复"直接要结果"'],
                "text": "Direct-result output should not include pause branch instructions.",
            },
        ],
        response="""
## Strengths
- Community insight
## Weaknesses
- No engineering lead
## Opportunities
- Growing demand
## Threats
- Fast-moving competitors
""".strip(),
    )

    grading = grade_run(run_dir)

    assert grading["summary"]["passed"] == 2
    assert grading["expectations"][0]["id"] == "all-quadrants"
    assert grading["expectations"][1]["passed"] is True


def test_grade_run_accepts_staged_interaction_or_full_result_expectation(tmp_path: Path) -> None:
    run_dir = write_run_fixture(
        tmp_path,
        assertions=[
            "The output preserves the staged interaction pattern or an explicit direct-result mode.",
        ],
        response="""
## Step 1

优势：
- 用户洞察

> 回复"继续"进入下一步，回复"不对"可修改，回复"直接要结果"可跳过检查。
""".strip(),
    )

    grading = grade_run(run_dir)

    assert grading["summary"]["passed"] == 1
    assert grading["expectations"][0]["id"] == "interaction-mode"
    assert grading["expectations"][0]["passed"] is True
