from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.reviews.cognitive_review import (
    build_human_review_packet,
    generate_release_recommendation,
    write_human_review_template,
)


def write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: SWOT 分析",
                "description: 使用 SWOT 结构分析决策。",
                "---",
                "",
                "# SWOT 分析",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-2"
    benchmark = {
        "metadata": {"skill_name": "SWOT 分析", "skill_path": "/tmp/swot"},
        "runs": [
            {
                "eval_id": 1,
                "eval_name": "ai-swot",
                "configuration": "with_skill",
                "run_number": 1,
                "result": {"pass_rate": 1.0, "passed": 3, "failed": 0, "total": 3, "time_seconds": 12.0, "tokens": 1200, "tool_calls": 0, "errors": 0},
                "expectations": [],
                "notes": [],
            },
            {
                "eval_id": 1,
                "eval_name": "ai-swot",
                "configuration": "with_skill",
                "run_number": 2,
                "result": {"pass_rate": 0.3333, "passed": 1, "failed": 2, "total": 3, "time_seconds": 15.0, "tokens": 1500, "tool_calls": 0, "errors": 0},
                "expectations": [],
                "notes": [],
            },
            {
                "eval_id": 1,
                "eval_name": "ai-swot",
                "configuration": "without_skill",
                "run_number": 1,
                "result": {"pass_rate": 0.6667, "passed": 2, "failed": 1, "total": 3, "time_seconds": 8.0, "tokens": 800, "tool_calls": 0, "errors": 0},
                "expectations": [],
                "notes": [],
            },
        ],
        "run_summary": {
            "with_skill": {"pass_rate": {"mean": 0.6667}, "time_seconds": {"mean": 13.5}, "tokens": {"mean": 1350}},
            "without_skill": {"pass_rate": {"mean": 0.6667}, "time_seconds": {"mean": 8.0}, "tokens": {"mean": 800}},
        },
        "notes": [],
    }
    (iteration_dir / "benchmark.json").parent.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "benchmark.json").write_text(json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8")

    stability = {
        "metadata": {"runs_per_configuration": 3},
        "overall": {"flags": ["weak_stability_value"]},
        "per_eval": [
            {
                "eval_id": 1,
                "eval_name": "ai-swot",
                "flags": ["unstable"],
                "configurations": {
                    "with_skill": {"expectation_variance": {}, "drift": {"drift_detected": True}},
                    "without_skill": {"expectation_variance": {}, "drift": {"drift_detected": False}},
                },
            }
        ],
    }
    (iteration_dir / "stability.json").write_text(json.dumps(stability, ensure_ascii=False, indent=2), encoding="utf-8")

    analysis = {
        "metadata": {"analyzer_model": "qwen-analyzer-test"},
        "per_eval": [
            {
                "eval_id": 1,
                "winner": "with_skill",
                "mechanism_findings": ["with_skill kept the intended structure but drifted across runs"],
                "instruction_use_signals": ["the step structure was visible in the best run"],
                "failure_tags": ["skill-content.reasoning-shallow"],
                "repair_layer": "skill-content",
                "summary": "reasoning depth still needs work",
            }
        ],
        "cross_eval_summary": {
            "overall_winner": "with_skill",
            "key_patterns": ["structure improved"],
            "critical_risks": ["stability is weak"],
        },
        "repair_recommendations": ["Strengthen reasoning depth and reduce drift."],
        "failure_tag_counts": {"skill-content.reasoning-shallow": 1},
    }
    (iteration_dir / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    run_specs = [
        ("with_skill", 1, "## Strengths\n- insight\n## Strategy\n- validate quickly"),
        ("with_skill", 2, "Strengths: insight\nWeaknesses: budget"),
        ("without_skill", 1, "可以尝试这个方向，但要先看清竞争。"),
    ]
    for configuration, run_number, response in run_specs:
        run_dir = iteration_dir / "eval-1-ai-swot" / configuration / f"run-{run_number}"
        (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
        (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
        (run_dir / "grading.json").write_text(
            json.dumps(
                {
                    "eval_id": 1,
                    "eval_name": "ai-swot",
                    "prompt": "Analyze this with SWOT.",
                    "output_file": str(run_dir / "outputs" / "final_response.md"),
                    "summary": {
                        "passed": 3 if run_number == 1 and configuration == "with_skill" else 1 if configuration == "with_skill" else 2,
                        "failed": 0 if run_number == 1 and configuration == "with_skill" else 2 if configuration == "with_skill" else 1,
                        "total": 3,
                        "pass_rate": 1.0 if run_number == 1 and configuration == "with_skill" else 0.3333 if configuration == "with_skill" else 0.6667,
                    },
                    "expectations": [],
                    "execution_metrics": {"total_tool_calls": 0, "errors_encountered": 0},
                    "timing": {"total_duration_seconds": 12.0},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return iteration_dir


def test_build_human_review_packet_selects_representative_runs_and_prefills_scores(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    packet = build_human_review_packet(iteration_dir, package_dir)

    assert packet["representative_runs"]["best_with_skill"]["run_number"] == 1
    assert packet["representative_runs"]["worst_with_skill"]["run_number"] == 2
    assert packet["representative_runs"]["baseline_comparison"]["configuration"] == "without_skill"
    assert "Protocol Fidelity" in packet["suggested_scores"]


def test_write_human_review_template_and_release_recommendation_respect_manual_decision(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    write_human_review_template(iteration_dir, package_name=package_dir.name)
    template = json.loads((iteration_dir / "human-review-score.json").read_text(encoding="utf-8"))
    assert template["decision"] == "hold"
    assert sorted(template["scores"].keys()) == sorted(
        [
            "Protocol Fidelity",
            "Structural Output",
            "Thinking Support",
            "Judgment Preservation",
            "Boundary Safety",
            "VisionTree Voice",
        ]
    )

    template["decision"] = "revise"
    template["reviewer"] = "tester"
    template["reviewed_at"] = "2026-04-08T12:00:00Z"
    (iteration_dir / "human-review-score.json").write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")

    recommendation = generate_release_recommendation(iteration_dir)

    assert recommendation["recommendation"] != "promote"
    assert "manual_review_decision:revise" in recommendation["blockers"]
    assert (iteration_dir / "release-recommendation.json").exists()
