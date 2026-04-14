from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.run_eval_pipeline import main, run_eval_pipeline


def write_certified_bundle_flow(base: Path) -> tuple[Path, Path]:
    factory_dir = base / "eval-factory"
    (factory_dir / "source-bank" / "sample").mkdir(parents=True)
    (factory_dir / "scenario-cards" / "sample").mkdir(parents=True)
    (factory_dir / "eval-candidates" / "sample").mkdir(parents=True)
    (factory_dir / "calibration-reports" / "sample").mkdir(parents=True)
    (factory_dir / "certified-evals" / "sample").mkdir(parents=True)

    (factory_dir / "source-bank" / "sample" / "source.json").write_text(
        json.dumps(
            {
                "source_id": "source-1",
                "task_family": "sample",
                "raw_text": "Analyze this decision with SWOT.",
                "source_type": "demo",
                "notes": "seed",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (factory_dir / "scenario-cards" / "sample" / "scenario.json").write_text(
        json.dumps(
            {
                "scenario_id": "scenario-1",
                "task_family": "sample",
                "source_ids": ["source-1"],
                "task_goal": "Help the user make a choice.",
                "user_state": "Wants a direct result.",
                "constraints": ["Low budget"],
                "hidden_tradeoff": "Speed versus confidence.",
                "boundary_axes": ["binary-forcing"],
                "acceptable_diversity_notes": "Good answers can still differ on recommendation.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (factory_dir / "eval-candidates" / "sample" / "candidate-101.json").write_text(
        json.dumps(
            {
                "eval_id": 101,
                "scenario_id": "scenario-1",
                "task_family": "sample",
                "variant_type": "base",
                "prompt": "Give me a direct SWOT result for this product idea.",
                "expected_output": "A full SWOT with strategy guidance.",
                "judge_rubric": ["Thinking Support"],
                "must_preserve": ["Respect direct-result mode."],
                "must_not_do": ["Avoid empty advice."],
                "expectations": [
                    {
                        "id": "all-quadrants",
                        "type": "contains_all",
                        "keywords": ["strengths", "weaknesses", "opportunities", "threats"],
                        "text": "Must include all four SWOT quadrants.",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (factory_dir / "eval-candidates" / "sample" / "candidate-102.json").write_text(
        json.dumps(
            {
                "eval_id": 102,
                "scenario_id": "scenario-1",
                "task_family": "sample",
                "variant_type": "paraphrase",
                "prompt": "Analyze this product idea with a direct SWOT recommendation.",
                "expected_output": "A full SWOT with strategy guidance.",
                "judge_rubric": ["Thinking Support"],
                "must_preserve": ["Respect direct-result mode."],
                "must_not_do": ["Avoid empty advice."],
                "expectations": [
                    {
                        "id": "all-quadrants",
                        "type": "contains_all",
                        "keywords": ["strengths", "weaknesses", "opportunities", "threats"],
                        "text": "Must include all four SWOT quadrants.",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (factory_dir / "calibration-reports" / "sample" / "bundle.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "report_id": "bundle-v0.1",
                    "bundle_id": "bundle-v0.1",
                    "package_name": "sample-package",
                    "task_family": "sample",
                    "calibrated_at": "2026-04-14T00:00:00+08:00",
                },
                "per_eval": [
                    {
                        "eval_id": 101,
                        "scenario_id": "scenario-1",
                        "strong_vs_weak_win_rate": 0.8,
                        "judge_agreement_score": 0.9,
                        "tie_rate": 0.2,
                        "discriminative_score": 0.8,
                        "notes": "good",
                    },
                    {
                        "eval_id": 102,
                        "scenario_id": "scenario-1",
                        "strong_vs_weak_win_rate": 0.82,
                        "judge_agreement_score": 0.88,
                        "tie_rate": 0.18,
                        "discriminative_score": 0.79,
                        "notes": "good",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    bundle_path = factory_dir / "certified-evals" / "sample" / "bundle.json"
    bundle_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "bundle_id": "bundle-v0.1",
                    "package_name": "sample-package",
                    "skill_name": "Sample Skill",
                    "task_family": "sample",
                    "certification_status": "certified",
                    "calibration_report_path": "calibration-reports/sample/bundle.json",
                },
                "thresholds": {
                    "strong_vs_weak_win_rate": 0.7,
                    "judge_agreement_score": 0.75,
                    "max_tie_rate": 0.6,
                },
                "evals": [
                    {
                        "eval_id": 101,
                        "scenario_id": "scenario-1",
                        "candidate_path": "eval-candidates/sample/candidate-101.json",
                        "variant_type": "base",
                        "certification_status": "certified",
                        "discriminative_score": 0.8,
                        "judge_agreement_score": 0.9,
                        "tie_rate": 0.2,
                        "strong_vs_weak_win_rate": 0.8,
                    },
                    {
                        "eval_id": 102,
                        "scenario_id": "scenario-1",
                        "candidate_path": "eval-candidates/sample/candidate-102.json",
                        "variant_type": "paraphrase",
                        "certification_status": "certified",
                        "discriminative_score": 0.79,
                        "judge_agreement_score": 0.88,
                        "tie_rate": 0.18,
                        "strong_vs_weak_win_rate": 0.82,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    package_dir = base / "packages" / "sample-package"
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "evals").mkdir(parents=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: Sample Skill",
                "description: Help the user analyze a decision with SWOT.",
                "---",
                "",
                "## 交互模式",
                "支持直接结果模式。",
                "",
                "### Step 0:",
                "信息不足时只问缺失项。",
                "",
                "### Step 1:",
                "输出四象限并暂停。",
                "",
                "### Step 2:",
                "排序并暂停。",
                "",
                "### Step 3:",
                "给出策略并暂停。",
                "",
                "## 输出格式",
                "Strengths / Weaknesses / Opportunities / Threats / Strategy",
                "",
                "## 规则",
                "信息充分时不要重复提问。",
            ]
        ),
        encoding="utf-8",
    )
    (package_dir / "metadata" / "package.json").write_text(
        json.dumps(
            {
                "package_name": "sample-package",
                "skill_name": "Sample Skill",
                "category": "strategy",
                "status": "candidate",
                "version": "0.1.0",
                "source_mode": "demo-only",
                "candidate_origin": "demo-migration",
                "eval_source": {
                    "mode": "certified-bundle",
                    "bundle_path": os.path.relpath(bundle_path, package_dir),
                    "sync_on_read": True,
                    "sync_output": "evals/evals.json",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return package_dir, base / "workspace"


def fake_execute_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    has_skill = "<SKILL_MD>" in payload["messages"][0]["content"] if payload["messages"] else False
    response = (
        "## Strengths\n- clear value\n## Weaknesses\n- small budget\n## Opportunities\n- real demand\n## Threats\n- competition\n## Strategy\n- validate the niche first"
        if has_skill
        else "## Strengths\n- clear value\n## Weaknesses\n- small budget\n## Opportunities\n- real demand\n## Threats\n- competition"
    )
    return {
        "choices": [{"message": {"content": response}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 150, "total_tokens": 270 if has_skill else 210},
    }


def fake_judge_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "winner": "A",
                            "margin": 0.8,
                            "confidence": 0.9,
                            "reasoning_summary": "Candidate A is more helpful.",
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
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180},
    }


def fake_analyzer_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "per_eval": [
                                {
                                    "eval_id": 101,
                                    "winner": "with_skill",
                                    "mechanism_findings": ["The skill added strategy guidance."],
                                    "instruction_use_signals": ["The skill preserved the SWOT structure."],
                                    "failure_tags": ["skill-content.reasoning-shallow"],
                                    "repair_layer": "skill-content",
                                    "summary": "The skill improves value but still needs deeper reasoning.",
                                }
                            ],
                            "cross_eval_summary": {
                                "overall_winner": "with_skill",
                                "key_patterns": ["with_skill consistently wins on actionability"],
                                "critical_risks": ["reasoning depth still limited"],
                            },
                            "repair_recommendations": [
                                {
                                    "category": "skill-content.reasoning-shallow",
                                    "repair_layer": "skill-content",
                                    "action": "Add deeper strategy examples.",
                                }
                            ],
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 150, "completion_tokens": 120, "total_tokens": 270},
    }


def test_run_eval_pipeline_runs_end_to_end_from_certified_bundle(tmp_path: Path) -> None:
    package_dir, workspace_dir = write_certified_bundle_flow(tmp_path)

    result = run_eval_pipeline(
        package_dir,
        workspace_dir,
        iteration_number=1,
        runs_per_configuration=1,
        sender=fake_execute_sender,
        judge_sender=fake_judge_sender,
        analyzer_sender=fake_analyzer_sender,
        api_key="test-key",
        model="qwen-exec-test",
        judge_model="qwen-judge-test",
        analyzer_model="qwen-analyzer-test",
    )

    iteration_dir = Path(result["iteration_dir"])
    assert result["eval_source_mode"] == "certified-bundle"
    assert (package_dir / "evals" / "evals.json").exists()
    assert (iteration_dir / "benchmark.json").exists()
    assert (iteration_dir / "differential-benchmark.json").exists()
    assert (iteration_dir / "level3-summary.json").exists()
    assert (iteration_dir / "stability.json").exists()
    assert (iteration_dir / "analysis.json").exists()
    assert (iteration_dir / "human-review-packet.md").exists()
    assert (iteration_dir / "release-recommendation.json").exists()
    assert result["level3_primary_mode"] == "differential"


def test_main_prints_pipeline_summary(monkeypatch, capsys, tmp_path: Path) -> None:
    expected = {
        "iteration_dir": str(tmp_path / "workspace" / "iteration-1"),
        "eval_source_mode": "certified-bundle",
        "level3_primary_mode": "differential",
    }

    def fake_run_eval_pipeline(package_dir: Path, workspace_dir: Path, **kwargs: object) -> dict:
        assert str(package_dir) == str(tmp_path / "packages" / "sample-package")
        assert str(workspace_dir) == str(tmp_path / "workspace")
        return expected

    monkeypatch.setattr("toolchain.run_eval_pipeline.run_eval_pipeline", fake_run_eval_pipeline)

    exit_code = main(
        [
            "--package-dir",
            str(tmp_path / "packages" / "sample-package"),
            "--workspace-dir",
            str(tmp_path / "workspace"),
            "--iteration-number",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected


def test_run_eval_pipeline_smoke_mode_limits_evals_and_runs(tmp_path: Path) -> None:
    package_dir, workspace_dir = write_certified_bundle_flow(tmp_path)

    result = run_eval_pipeline(
        package_dir,
        workspace_dir,
        iteration_number=1,
        smoke=True,
        sender=fake_execute_sender,
        judge_sender=fake_judge_sender,
        analyzer_sender=fake_analyzer_sender,
        api_key="test-key",
        model="qwen-exec-test",
        judge_model="qwen-judge-test",
        analyzer_model="qwen-analyzer-test",
    )

    iteration_dir = Path(result["iteration_dir"])
    eval_dirs = sorted(path.name for path in iteration_dir.glob("eval-*"))

    assert result["smoke_mode"] is True
    assert result["runs_per_configuration"] == 1
    assert result["skip_completed"] is True
    assert result["selected_eval_count"] == 2
    assert len(eval_dirs) == 2
    assert len(result["completed_runs"]) == 4


def test_main_passes_smoke_arguments(monkeypatch, capsys, tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    def fake_run_eval_pipeline(package_dir: Path, workspace_dir: Path, **kwargs: object) -> dict:
        observed["package_dir"] = str(package_dir)
        observed["workspace_dir"] = str(workspace_dir)
        observed.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr("toolchain.run_eval_pipeline.run_eval_pipeline", fake_run_eval_pipeline)

    exit_code = main(
        [
            "--package-dir",
            str(tmp_path / "packages" / "sample-package"),
            "--workspace-dir",
            str(tmp_path / "workspace"),
            "--iteration-number",
            "1",
            "--smoke",
            "--max-evals",
            "2",
            "--eval-ids",
            "101,102",
            "--skip-completed",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {"ok": True}
    assert observed["smoke"] is True
    assert observed["max_evals"] == 2
    assert observed["eval_ids"] == [101, 102]
    assert observed["skip_completed"] is True
