from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.quantitative.run_quantitative_bundle import run_quantitative_bundle
from toolchain.quantitative.skill_structure_score import score_skill_structure


def write_package(base: Path) -> Path:
    package_dir = base / "sample-package"
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "metadata" / "package.json").write_text(
        json.dumps({"package_name": "sample-package", "skill_name": "Sample Skill"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: Sample Skill",
                "description: Use this skill when the user needs direct decision help.",
                "---",
                "",
                "# Sample Skill",
                "",
                "## Workflow",
                "",
                "### Step 1",
                "Read the input and detect missing-info.",
                "",
                "### Step 2",
                "Use direct-result mode when information is sufficient.",
                "",
                "### Step 3",
                "Use staged follow-up with checkpoint, continue, and revise branches when needed.",
                "",
                "## Output",
                "",
                "Return a list, recommendation, and action item structure.",
                "",
                "## Guardrails",
                "",
                "Do not overstate certainty. If risk appears, handle it with a fallback.",
                "",
                "## Example",
                "",
                "Input: Help me decide. Output: recommendation with tradeoff.",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def write_run(run_dir: Path, response: str, tokens: int) -> None:
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
    (run_dir / "request.json").write_text("{}", encoding="utf-8")
    (run_dir / "transcript.json").write_text(json.dumps({"assistant_response": response}), encoding="utf-8")
    (run_dir / "raw_response.json").write_text(json.dumps({"response": response}), encoding="utf-8")
    (run_dir / "timing.json").write_text(
        json.dumps({"total_duration_seconds": 1, "total_tokens": tokens}),
        encoding="utf-8",
    )


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-sample"
    eval_dir.mkdir(parents=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "sample",
                "prompt": "Help me decide.",
                "expected_output": "A useful answer.",
                "assertions": [{"id": "non-empty", "type": "contains_any", "keywords": [], "text": "non-empty"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_run(eval_dir / "with_skill" / "run-1", "A useful answer with tradeoffs.", 100)
    write_run(eval_dir / "without_skill" / "run-1", "A generic answer.", 80)
    return iteration_dir


def fake_judge_sender(payload: dict) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "winner": "A",
                            "margin": 0.7,
                            "confidence": 0.8,
                            "reasoning_summary": "A is better.",
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


def test_run_quantitative_bundle_writes_supporting_summary(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    result = run_quantitative_bundle(
        iteration_dir,
        package_dir,
        sender=fake_judge_sender,
        judge_model="kimi-for-coding",
    )

    assert result["quantitative_summary"]["metadata"]["role"] == "supporting-evidence"
    assert result["quantitative_summary"]["structural_diagnostics"]["role"] == "diagnostic-only"
    assert result["quantitative_summary"]["weighted_structure_score"]["role"] == "diagnostic-only"
    assert (iteration_dir / "benchmark.json").exists()
    assert (iteration_dir / "differential-benchmark.json").exists()
    assert (iteration_dir / "level3-summary.json").exists()
    assert (iteration_dir / "stability.json").exists()
    assert (iteration_dir / "quantitative-summary.json").exists()
    assert (iteration_dir / "quantitative-summary.md").exists()


def test_score_skill_structure_uses_darwin_dimensions_as_diagnostics(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")

    report = score_skill_structure(package_dir)

    assert report["source"] == "darwin-skill dimensions 1-6"
    assert report["role"] == "diagnostic-only"
    assert report["weighted_structure_score"]["max_score"] == 60
    assert [item["id"] for item in report["dimensions"]] == [
        "frontmatter_quality",
        "workflow_clarity",
        "boundary_coverage",
        "checkpoint_design",
        "instruction_specificity",
        "resource_integration",
    ]
