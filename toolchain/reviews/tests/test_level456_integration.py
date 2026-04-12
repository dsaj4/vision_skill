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
                "name: SWOT 分析",
                "description: 使用 SWOT 结构分析决策。",
                "---",
                "",
                "## 交互模式",
                "分步执行；支持直接要结果。",
                "",
                "### Step 0:",
                "判断信息是否充分，不足时只追问缺失项。",
                "",
                "### Step 1:",
                "输出四象限并暂停确认。",
                "",
                "### Step 2:",
                "做优先级排序并暂停确认。",
                "",
                "### Step 3:",
                "给出交叉策略并暂停确认。",
                "",
                "## 输出格式",
                "输出 Strengths / Weaknesses / Opportunities / Threats / Strategy。",
                "",
                "## 规则",
                "信息充分时禁止重复提问；每步完成后必须暂停确认。",
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
                "prompt": "请直接给我 SWOT 结果。",
                "expected_output": "完整 SWOT",
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
                json.dumps({"model": "qwen-test", "messages": [{"role": "user", "content": "请直接给我 SWOT 结果。"}]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (run_dir / "transcript.json").write_text(
                json.dumps(
                    {
                        "configuration": configuration,
                        "messages": [{"role": "user", "content": "请直接给我 SWOT 结果。"}],
                        "assistant_response": response,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (run_dir / "raw_response.json").write_text(
                json.dumps({"choices": [{"message": {"content": response}}], "usage": {"total_tokens": 800}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (run_dir / "timing.json").write_text(
                json.dumps({"total_tokens": 900 if configuration == "with_skill" else 700, "total_duration_seconds": 10.0 + index}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    return iteration_dir


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
                                    "mechanism_findings": ["the skill improved structure but remained unstable"],
                                    "instruction_use_signals": ["the skill shaped the output sections"],
                                    "failure_tags": ["skill-content.reasoning-shallow"],
                                    "repair_layer": "skill-content",
                                    "summary": "good structure, weak consistency",
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

    grade_iteration_runs(iteration_dir, skill_name="SWOT 分析", skill_path=str(package_dir))
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
