from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.analyzers.mechanism_analyzer import analyze_iteration
from toolchain.benchmarks.run_benchmark import grade_iteration_runs
from toolchain.benchmarks.stability import generate_stability_report, write_stability_artifacts
from toolchain.reviews.cognitive_review import (
    build_human_review_packet,
    generate_release_recommendation,
    write_human_review_template,
)


def write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    (package_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (package_dir / "evals").mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: SWOT Analysis",
                "description: Help the user think through a decision with SWOT.",
                "---",
                "",
                "## Interaction Mode",
                "Support staged interaction and direct-result mode.",
                "",
                "### Step 0:",
                "Ask only for missing information when necessary.",
                "",
                "### Step 1:",
                "Draft the four quadrants and pause for confirmation.",
                "",
                "### Step 2:",
                "Prioritize insights and pause for confirmation.",
                "",
                "### Step 3:",
                "Propose cross-quadrant strategy and pause for confirmation.",
                "",
                "## Output Format",
                "Output Strengths / Weaknesses / Opportunities / Threats / Strategy.",
                "",
                "## Rules",
                "Do not repeat questions when information is sufficient.",
                "Pause after each staged step.",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot",
                "prompt": "Give me a direct SWOT result for an AI note-taking app.",
                "expected_output": "A complete SWOT with strategy guidance.",
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
                        "keywords": ["strategy", "actions"],
                        "text": "Must include strategy guidance.",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with_skill_responses = [
        "## Strengths\n- insight\n## Weaknesses\n- budget\n## Opportunities\n- demand\n## Threats\n- competitors\n## Strategy\n- validate quickly",
        "## Strengths\n- insight\n## Weaknesses\n- budget\n## Opportunities\n- demand\n## Threats\n- competitors\n## Strategy\n- validate quickly",
        "Strengths: insight\nWeaknesses: budget\nOpportunities: demand\nThreats: competitors",
    ]
    without_skill_responses = [
        "## Strengths\n- insight\n## Weaknesses\n- budget\n## Opportunities\n- demand\n## Threats\n- competitors",
        "## Strengths\n- insight\n## Weaknesses\n- budget\n## Opportunities\n- demand\n## Threats\n- competitors",
        "## Strengths\n- insight\n## Weaknesses\n- budget\n## Opportunities\n- demand\n## Threats\n- competitors",
    ]

    for configuration, responses in (("with_skill", with_skill_responses), ("without_skill", without_skill_responses)):
        for index, response in enumerate(responses, start=1):
            run_dir = eval_dir / configuration / f"run-{index}"
            (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
            (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
            (run_dir / "request.json").write_text(
                json.dumps(
                    {
                        "model": "qwen-test",
                        "messages": [{"role": "user", "content": "Give me the SWOT result."}],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (run_dir / "transcript.json").write_text(
                json.dumps(
                    {
                        "configuration": configuration,
                        "messages": [{"role": "user", "content": "Give me the SWOT result."}],
                        "assistant_response": response,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (run_dir / "raw_response.json").write_text(
                json.dumps(
                    {
                        "choices": [{"message": {"content": response}}],
                        "usage": {"total_tokens": 800},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (run_dir / "timing.json").write_text(
                json.dumps(
                    {
                        "total_tokens": 900 if configuration == "with_skill" else 700,
                        "total_duration_seconds": 10.0 + index,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    return iteration_dir


def write_level3_summary(iteration_dir: Path) -> None:
    eval_dir = iteration_dir / "eval-1-swot"
    (iteration_dir / "level3-summary.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "iteration_dir": str(iteration_dir),
                    "skill_name": "SWOT Analysis",
                    "skill_path": str(iteration_dir.parent.parent / "packages" / "swot-analysis"),
                    "generated_at": "2026-04-14T00:00:00Z",
                    "eval_ids": [1],
                },
                "primary_mode": "differential",
                "primary_artifact_path": str(iteration_dir / "differential-benchmark.json"),
                "supporting_gate_artifact_path": str(iteration_dir / "benchmark.json"),
                "pairwise_summary": {
                    "win_rate": 0.6667,
                    "tie_rate": 0.0,
                    "avg_margin": 0.3667,
                    "judge_disagreement_rate": 0.0,
                    "cost_adjusted_value": 0.05,
                },
                "gate_summary": {
                    "with_skill": {"pass_rate": {"mean": 0.8333}},
                    "without_skill": {"pass_rate": {"mean": 0.5}},
                },
                "per_eval": [
                    {
                        "eval_id": 1,
                        "eval_name": "swot",
                        "run_number": 1,
                        "final_winner": "with_skill",
                        "avg_margin": 0.45,
                        "judge_disagreement": False,
                        "with_skill_run_dir": str(eval_dir / "with_skill" / "run-1"),
                        "without_skill_run_dir": str(eval_dir / "without_skill" / "run-1"),
                    },
                    {
                        "eval_id": 1,
                        "eval_name": "swot",
                        "run_number": 2,
                        "final_winner": "with_skill",
                        "avg_margin": 0.4,
                        "judge_disagreement": False,
                        "with_skill_run_dir": str(eval_dir / "with_skill" / "run-2"),
                        "without_skill_run_dir": str(eval_dir / "without_skill" / "run-2"),
                    },
                    {
                        "eval_id": 1,
                        "eval_name": "swot",
                        "run_number": 3,
                        "final_winner": "without_skill",
                        "avg_margin": 0.25,
                        "judge_disagreement": False,
                        "with_skill_run_dir": str(eval_dir / "with_skill" / "run-3"),
                        "without_skill_run_dir": str(eval_dir / "without_skill" / "run-3"),
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def fake_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "per_eval": [
                                {
                                    "eval_id": 1,
                                    "winner": "with_skill",
                                    "mechanism_findings": ["The skill improved structure but remained unstable."],
                                    "instruction_use_signals": ["The skill shaped the output sections."],
                                    "failure_tags": ["skill-content.reasoning-shallow"],
                                    "repair_layer": "skill-content",
                                    "summary": "Good structure, weak consistency.",
                                }
                            ],
                            "cross_eval_summary": {
                                "overall_winner": "with_skill",
                                "key_patterns": ["structure improved"],
                                "critical_risks": ["instability persists"],
                            },
                            "repair_recommendations": ["Add stronger strategy examples and reduce drift."],
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 120, "total_tokens": 220},
    }


def test_level456_pipeline_runs_end_to_end_on_synthetic_iteration(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    grade_iteration_runs(iteration_dir, skill_name="SWOT Analysis", skill_path=str(package_dir))
    write_level3_summary(iteration_dir)
    stability = generate_stability_report(iteration_dir)
    write_stability_artifacts(iteration_dir, stability)
    analyze_iteration(iteration_dir, package_dir, sender=fake_sender, api_key="test-key", analyzer_model="qwen-analyzer-test")
    packet = build_human_review_packet(iteration_dir, package_dir)
    write_human_review_template(iteration_dir, package_name=package_dir.name)
    recommendation = generate_release_recommendation(iteration_dir)

    assert (iteration_dir / "benchmark.json").exists()
    assert (iteration_dir / "stability.json").exists()
    assert (iteration_dir / "analysis.json").exists()
    assert (iteration_dir / "human-review-packet.md").exists()
    assert (iteration_dir / "human-review-score.json").exists()
    assert (iteration_dir / "release-recommendation.json").exists()
    assert packet["representative_runs"]["best_with_skill"]["configuration"] == "with_skill"
    assert recommendation["recommendation"] in {"hold", "pending-human-review"}
