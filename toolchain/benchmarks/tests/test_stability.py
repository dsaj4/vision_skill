from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.stability import generate_stability_report, write_stability_artifacts


def write_run(
    run_dir: Path,
    *,
    pass_rate: float,
    passed: int,
    failed: int,
    total: int,
    seconds: float,
    tokens: int,
    response: str,
    expectations: list[dict[str, object]],
) -> None:
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
    (run_dir / "grading.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "stability-case",
                "prompt": "Analyze this with SWOT.",
                "output_file": str(run_dir / "outputs" / "final_response.md"),
                "expectations": expectations,
                "summary": {
                    "passed": passed,
                    "failed": failed,
                    "total": total,
                    "pass_rate": pass_rate,
                },
                "execution_metrics": {
                    "response_character_count": len(response),
                    "response_word_count": len(response.split()),
                    "markdown_heading_count": response.count("## "),
                    "total_tool_calls": 0,
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


def write_iteration(tmp_path: Path) -> Path:
    iteration_dir = tmp_path / "iteration-1"
    eval_dir = iteration_dir / "eval-1-stability-case"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "stability-case",
                "prompt": "Analyze this with SWOT.",
                "expected_output": "Structured SWOT result.",
                "assertions": [
                    "The output includes strengths, weaknesses, opportunities, and threats.",
                    "The output includes strategy guidance rather than only listing factors.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    stable_baseline_response = """
## Strengths
- community insight
## Weaknesses
- low budget
## Opportunities
- demand growth
## Threats
- strong competitors
## Strategy
- validate demand quickly
""".strip()

    drifting_with_skill_response = """
Strengths: community insight
Weaknesses: low budget
Opportunities: demand growth
Threats: strong competitors
""".strip()

    expectation_pass = [
        {
            "id": "swot-quadrants",
            "text": "quadrants",
            "type": "contains_all_groups",
            "passed": True,
            "evidence": "ok",
        },
        {
            "id": "strategy-guidance",
            "text": "strategy",
            "type": "contains_any",
            "passed": True,
            "evidence": "ok",
        },
    ]
    expectation_partial = [
        {
            "id": "swot-quadrants",
            "text": "quadrants",
            "type": "contains_all_groups",
            "passed": True,
            "evidence": "ok",
        },
        {
            "id": "strategy-guidance",
            "text": "strategy",
            "type": "contains_any",
            "passed": False,
            "evidence": "missing",
        },
    ]

    write_run(
        eval_dir / "with_skill" / "run-1",
        pass_rate=1.0,
        passed=2,
        failed=0,
        total=2,
        seconds=20.0,
        tokens=2200,
        response=stable_baseline_response,
        expectations=expectation_pass,
    )
    write_run(
        eval_dir / "with_skill" / "run-2",
        pass_rate=1.0,
        passed=2,
        failed=0,
        total=2,
        seconds=22.0,
        tokens=2300,
        response=stable_baseline_response,
        expectations=expectation_pass,
    )
    write_run(
        eval_dir / "with_skill" / "run-3",
        pass_rate=0.5,
        passed=1,
        failed=1,
        total=2,
        seconds=28.0,
        tokens=2800,
        response=drifting_with_skill_response,
        expectations=expectation_partial,
    )

    write_run(
        eval_dir / "without_skill" / "run-1",
        pass_rate=1.0,
        passed=2,
        failed=0,
        total=2,
        seconds=10.0,
        tokens=1100,
        response=stable_baseline_response,
        expectations=expectation_pass,
    )
    write_run(
        eval_dir / "without_skill" / "run-2",
        pass_rate=1.0,
        passed=2,
        failed=0,
        total=2,
        seconds=11.0,
        tokens=1150,
        response=stable_baseline_response,
        expectations=expectation_pass,
    )
    write_run(
        eval_dir / "without_skill" / "run-3",
        pass_rate=1.0,
        passed=2,
        failed=0,
        total=2,
        seconds=12.0,
        tokens=1200,
        response=stable_baseline_response,
        expectations=expectation_pass,
    )
    return iteration_dir


def test_generate_stability_report_detects_variance_drift_and_cost_risk(tmp_path: Path) -> None:
    iteration_dir = write_iteration(tmp_path)

    report = generate_stability_report(iteration_dir)

    assert report["metadata"]["runs_per_configuration"] == 3
    assert report["overall"]["configurations"]["with_skill"]["pass_rate"]["mean"] == 0.8333
    assert report["overall"]["flags"]
    assert "weak_stability_value" in report["overall"]["flags"]

    per_eval = report["per_eval"][0]
    assert per_eval["configurations"]["with_skill"]["drift"]["drift_detected"] is True
    assert per_eval["configurations"]["with_skill"]["expectation_variance"]["strategy-guidance"]["unstable"] is True
    assert "unstable" in per_eval["flags"]


def test_write_stability_artifacts_writes_expected_files(tmp_path: Path) -> None:
    iteration_dir = write_iteration(tmp_path)
    report = generate_stability_report(iteration_dir)

    write_stability_artifacts(iteration_dir, report)

    assert (iteration_dir / "stability.json").exists()
    assert (iteration_dir / "stability.md").exists()
    assert (iteration_dir / "variance-by-expectation.json").exists()
