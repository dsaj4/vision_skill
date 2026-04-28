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
    record_human_authorization,
    write_human_review_authorization_template,
    write_human_review_template,
)


def write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: SWOT Analysis",
                "description: Use SWOT to help the user analyze a decision.",
                "---",
                "",
                "# SWOT Analysis",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def write_iteration(base: Path, *, hard_gate_passed: bool = True, deep_eval_decision: str = "revise") -> Path:
    iteration_dir = base / "iteration-2"
    benchmark = {
        "metadata": {"skill_name": "SWOT Analysis", "skill_path": "/tmp/swot"},
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
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "benchmark.json").write_text(json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8")
    (iteration_dir / "level3-summary.json").write_text(
        json.dumps(
            {
                "metadata": {"skill_name": "SWOT Analysis"},
                "primary_mode": "differential",
                "pairwise_summary": {
                    "win_rate": 0.5,
                    "tie_rate": 0.0,
                    "avg_margin": 0.05,
                    "judge_disagreement_rate": 0.0,
                    "cost_adjusted_value": -0.1,
                },
                "gate_summary": benchmark["run_summary"],
                "per_eval": [
                    {
                        "eval_id": 1,
                        "eval_name": "ai-swot",
                        "run_number": 1,
                        "final_winner": "with_skill",
                        "avg_margin": 0.9,
                        "judge_disagreement": False,
                        "with_skill_run_dir": str(iteration_dir / "eval-1-ai-swot" / "with_skill" / "run-1"),
                        "without_skill_run_dir": str(iteration_dir / "eval-1-ai-swot" / "without_skill" / "run-1"),
                    },
                    {
                        "eval_id": 1,
                        "eval_name": "ai-swot",
                        "run_number": 2,
                        "final_winner": "without_skill",
                        "avg_margin": 0.8,
                        "judge_disagreement": False,
                        "with_skill_run_dir": str(iteration_dir / "eval-1-ai-swot" / "with_skill" / "run-2"),
                        "without_skill_run_dir": str(iteration_dir / "eval-1-ai-swot" / "without_skill" / "run-1"),
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (iteration_dir / "stability.json").write_text(
        json.dumps({"overall": {"flags": ["weak_stability_value"]}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (iteration_dir / "analysis.json").write_text(
        json.dumps(
            {
                "cross_eval_summary": {"overall_winner": "with_skill"},
                "repair_recommendations": ["Strengthen reasoning depth and reduce drift."],
                "per_eval": [
                    {
                        "eval_id": 1,
                        "failure_tags": ["skill-content.reasoning-shallow"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (iteration_dir / "hard-gate.json").write_text(
        json.dumps(
            {
                "passed": hard_gate_passed,
                "blockers": [] if hard_gate_passed else ["missing_artifact"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (iteration_dir / "quantitative-summary.json").write_text(
        json.dumps(
            {
                "supporting_risks": ["cost_adjusted_value remains negative"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (iteration_dir / "deep-eval.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "quality_primary_mode": "deep-quality",
                },
                "release_signal": {
                    "decision": deep_eval_decision,
                    "confidence": 0.7,
                    "reasons": ["live-test quality is not strong enough"] if deep_eval_decision != "pass" else ["quality is strong enough"],
                },
                "repair_recommendations": ["Tighten direct-result behavior."],
                "per_eval": [
                    {
                        "eval_id": 1,
                        "winner": "with_skill" if deep_eval_decision == "pass" else "tie",
                        "failure_tags": [] if deep_eval_decision == "pass" else ["skill-content.reasoning-shallow"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (iteration_dir / "deep-eval.md").write_text("# Deep Eval\n\n- decision\n", encoding="utf-8")

    run_specs = [
        ("with_skill", 1, "## Strengths\n- insight\n## Strategy\n- validate quickly"),
        ("with_skill", 2, "Strengths: insight\nWeaknesses: budget"),
        ("without_skill", 1, "Try the direction, but check competition first."),
    ]
    for configuration, run_number, response in run_specs:
        run_dir = iteration_dir / "eval-1-ai-swot" / configuration / f"run-{run_number}"
        (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
        (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
        (run_dir / "grading.json").write_text(
            json.dumps(
                {
                    "summary": {
                        "pass_rate": 1.0 if configuration == "with_skill" and run_number == 1 else 0.3333 if configuration == "with_skill" else 0.6667,
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return iteration_dir


def fake_review_sender(payload: dict) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": "\n".join(
                        [
                            "# Human Review Packet",
                            "",
                            "## 最终审阅结论摘要",
                            "",
                            "- 当前建议：先按 agent 报告做人工判断。",
                            "",
                            "## 关键发现",
                            "",
                            "- with_skill 在最佳样本里价值更强。",
                            "- quantitative 仍有成本风险。",
                            "",
                            "## 主要风险与阻塞",
                            "",
                            "- deep eval 仍建议 revise。",
                            "",
                            "## 修补建议",
                            "",
                            "- Tighten direct-result behavior.",
                            "",
                            "## 证据索引",
                            "",
                            "- 以 deep-eval.json 为主。",
                        ]
                    )
                }
            }
        ]
    }


def test_build_human_review_packet_writes_llm_markdown_and_agent_report(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    packet = build_human_review_packet(iteration_dir, package_dir, sender=fake_review_sender)

    assert packet["representative_runs"]["best_with_skill"]["run_number"] == 1
    assert packet["representative_runs"]["worst_with_skill"]["run_number"] == 2
    assert packet["summary"]["suggested_human_decision"] == "revise"
    assert (iteration_dir / "agent-review-report.json").exists()
    assert (iteration_dir / "human-review-packet.md").exists()

    markdown = (iteration_dir / "human-review-packet.md").read_text(encoding="utf-8")
    report = json.loads((iteration_dir / "agent-review-report.json").read_text(encoding="utf-8"))
    assert "# Human Review Packet" in markdown
    assert "最终审阅结论摘要" in markdown
    assert report["metadata"]["report_id"]
    assert report["key_findings"]


def test_write_human_review_authorization_template_defaults_to_pending(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")
    build_human_review_packet(iteration_dir, package_dir, sender=fake_review_sender)

    template = write_human_review_authorization_template(iteration_dir, package_name=package_dir.name)
    recommendation = generate_release_recommendation(iteration_dir)

    assert template["decision"] == "pending"
    assert template["authorization_source"] == "conversation"
    assert recommendation["minimum_gates"]["human_review_completed"] is False
    assert recommendation["recommendation"] == "pending-human-review"


def test_record_human_authorization_writes_conversation_decision(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")
    build_human_review_packet(iteration_dir, package_dir, sender=fake_review_sender)

    authorization = record_human_authorization(iteration_dir, decision="approve", notes="Looks good.")

    assert authorization["decision"] == "approve"
    assert authorization["reviewer"] == "conversation-user"
    assert authorization["authorization_source"] == "conversation"
    assert authorization["agent_report_id"]


def test_generate_release_recommendation_allows_manual_approve_to_override_revise(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace", deep_eval_decision="revise")
    build_human_review_packet(iteration_dir, package_dir, sender=fake_review_sender)
    record_human_authorization(iteration_dir, decision="approve")

    recommendation = generate_release_recommendation(iteration_dir)

    assert recommendation["minimum_gates"]["human_review_completed"] is True
    assert recommendation["recommendation"] == "promote"
    assert "manual_review_decision:revise" not in recommendation["blockers"]


def test_generate_release_recommendation_keeps_hard_blocker_even_with_approve(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace", hard_gate_passed=False, deep_eval_decision="pass")
    build_human_review_packet(iteration_dir, package_dir, sender=fake_review_sender)
    record_human_authorization(iteration_dir, decision="approve")

    recommendation = generate_release_recommendation(iteration_dir)

    assert recommendation["recommendation"] == "hold"
    assert "hard_gate_failed" in recommendation["blockers"]


def test_generate_release_recommendation_keeps_deep_eval_hold_blocker_even_with_approve(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace", deep_eval_decision="hold")
    build_human_review_packet(iteration_dir, package_dir, sender=fake_review_sender)
    record_human_authorization(iteration_dir, decision="approve")

    recommendation = generate_release_recommendation(iteration_dir)

    assert recommendation["recommendation"] == "hold"
    assert "deep_eval_decision:hold" in recommendation["blockers"]


def test_generate_release_recommendation_supports_legacy_human_review_score_fallback(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace", deep_eval_decision="pass")
    build_human_review_packet(iteration_dir, package_dir, sender=fake_review_sender)
    write_human_review_template(iteration_dir, package_name=package_dir.name)
    legacy = json.loads((iteration_dir / "human-review-score.json").read_text(encoding="utf-8"))
    legacy["decision"] = "pass"
    legacy["reviewer"] = "tester"
    legacy["reviewed_at"] = "2026-04-28T10:00:00Z"
    (iteration_dir / "human-review-score.json").write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")

    recommendation = generate_release_recommendation(iteration_dir)

    assert recommendation["minimum_gates"]["human_review_completed"] is True
    assert recommendation["human_review"]["source"] == "legacy-human-review-score"
    assert recommendation["recommendation"] == "promote"


def test_generate_release_recommendation_treats_authorization_report_mismatch_as_pending(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace", deep_eval_decision="pass")
    build_human_review_packet(iteration_dir, package_dir, sender=fake_review_sender)
    template = write_human_review_authorization_template(iteration_dir, package_name=package_dir.name)
    template["decision"] = "approve"
    template["reviewer"] = "tester"
    template["authorized_at"] = "2026-04-28T10:00:00Z"
    template["agent_report_id"] = "stale-report"
    (iteration_dir / "human-review-authorization.json").write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")

    recommendation = generate_release_recommendation(iteration_dir)

    assert recommendation["minimum_gates"]["human_review_completed"] is False
    assert recommendation["recommendation"] == "pending-human-review"
    assert "human_review_report_mismatch" in recommendation["blockers"]
