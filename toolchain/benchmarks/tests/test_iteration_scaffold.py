from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.iteration_scaffold import prepare_iteration


def write_package_with_evals(base: Path) -> Path:
    package_dir = base / "example-package"
    (package_dir / "evals").mkdir(parents=True)
    (package_dir / "metadata").mkdir(parents=True)

    (package_dir / "metadata" / "package.json").write_text(
        json.dumps(
            {
                "package_name": "example-package",
                "skill_name": "Example Skill",
                "category": "strategy",
                "status": "candidate",
                "version": "0.1.0",
                "source_mode": "demo-only",
                "candidate_origin": "demo-migration",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "evals" / "evals.json").write_text(
        json.dumps(
            {
                "skill_name": "Example Skill",
                "evals": [
                    {
                        "id": 1,
                        "prompt": "Please analyze this decision with SWOT.",
                        "expected_output": "Structured SWOT output.",
                        "files": [],
                        "expectations": ["Includes all four SWOT quadrants."],
                        "execution_eval": {
                            "enabled": True,
                            "turn_script": [
                                {"label": "staged", "text": "Start with the first step."},
                                {"label": "continue", "text": "Continue."},
                            ],
                        },
                        "host_eval": {
                            "enabled": True,
                            "turn_script": [{"text": "Run Kimi host validation."}],
                            "expected_trigger": True,
                            "expected_trigger_signals": ["proxy_skill_read"],
                            "expected_protocol_path": "direct-result -> no-checkpoint",
                        },
                    },
                    {
                        "id": 2,
                        "prompt": "Direct result mode SWOT please.",
                        "expected_output": "Direct result without checkpoint pauses.",
                        "files": [],
                        "expectations": ["Respects direct-result mode."],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return package_dir


def test_prepare_iteration_creates_eval_directories_and_metadata(tmp_path: Path) -> None:
    package_dir = write_package_with_evals(tmp_path)
    workspace_dir = tmp_path / "example-package-workspace"

    result = prepare_iteration(package_dir, workspace_dir, iteration_number=1, runs_per_configuration=1)

    iteration_dir = workspace_dir / "iteration-1"
    eval_dir = iteration_dir / "eval-1-please-analyze-this-decision-with-swot"

    assert result["created"] is True
    assert iteration_dir.exists()
    assert eval_dir.exists()
    assert (eval_dir / "eval_metadata.json").exists()
    assert (eval_dir / "with_skill" / "run-1" / "outputs").exists()
    assert (eval_dir / "without_skill" / "run-1" / "outputs").exists()
    metadata = json.loads((eval_dir / "eval_metadata.json").read_text(encoding="utf-8"))
    assert metadata["execution_eval"]["enabled"] is True
    assert metadata["execution_eval"]["turn_script"][1]["label"] == "continue"
    assert metadata["host_eval"]["enabled"] is True


def test_prepare_iteration_updates_history_with_prepared_iteration(tmp_path: Path) -> None:
    package_dir = write_package_with_evals(tmp_path)
    workspace_dir = tmp_path / "example-package-workspace"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "history.json").write_text(
        json.dumps(
            {
                "started_at": "2026-04-08T00:00:00+08:00",
                "package_name": "example-package",
                "skill_name": "Example Skill",
                "current_best": "candidate-seed",
                "iterations": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    prepare_iteration(package_dir, workspace_dir, iteration_number=1, runs_per_configuration=1)

    history = json.loads((workspace_dir / "history.json").read_text(encoding="utf-8"))
    assert history["iterations"][0]["version"] == "iteration-1"
    assert history["iterations"][0]["stage"] == "prepared"


def test_prepare_iteration_prefers_certified_bundle_when_package_declares_eval_source(tmp_path: Path) -> None:
    factory_dir = tmp_path / "eval-factory"
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
                "raw_text": "raw prompt",
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
                "task_goal": "Goal",
                "user_state": "State",
                "constraints": ["Constraint"],
                "hidden_tradeoff": "Tradeoff",
                "boundary_axes": ["Axis"],
                "acceptable_diversity_notes": "Notes",
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
                "prompt": "Certified prompt",
                "expected_output": "Certified output",
                "judge_rubric": ["Thinking Support"],
                "must_preserve": ["Preserve"],
                "must_not_do": ["Don't"],
                "expectations": ["The output is non-empty."],
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
                    "package_name": "example-package",
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
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    certified_bundle_path = factory_dir / "certified-evals" / "sample" / "bundle.json"
    certified_bundle_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "bundle_id": "bundle-v0.1",
                    "package_name": "example-package",
                    "skill_name": "Example Skill",
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
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    package_dir = tmp_path / "example-package"
    (package_dir / "evals").mkdir(parents=True)
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "metadata" / "package.json").write_text(
        json.dumps(
            {
                "package_name": "example-package",
                "skill_name": "Example Skill",
                "category": "strategy",
                "status": "candidate",
                "version": "0.1.0",
                "source_mode": "demo-only",
                "candidate_origin": "demo-migration",
                "eval_source": {
                    "mode": "certified-bundle",
                    "bundle_path": os.path.relpath(certified_bundle_path, package_dir),
                    "sync_on_read": True,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "evals" / "evals.json").write_text(
        json.dumps(
            {
                "skill_name": "Example Skill",
                "evals": [
                    {
                        "id": 1,
                        "prompt": "stale prompt",
                        "expected_output": "stale output",
                        "files": [],
                        "expectations": ["stale"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    workspace_dir = tmp_path / "example-package-workspace"

    result = prepare_iteration(package_dir, workspace_dir, iteration_number=1, runs_per_configuration=1)

    assert result["created"] is True
    assert (workspace_dir / "iteration-1" / "eval-101-certified-prompt").exists()
    assert not (workspace_dir / "iteration-1" / "eval-1-stale-prompt").exists()


def test_prepare_iteration_supports_eval_filtering_for_smoke_mode(tmp_path: Path) -> None:
    package_dir = write_package_with_evals(tmp_path)
    workspace_dir = tmp_path / "example-package-workspace"

    result = prepare_iteration(
        package_dir,
        workspace_dir,
        iteration_number=1,
        runs_per_configuration=1,
        eval_ids=[2],
        max_evals=1,
    )

    iteration_dir = workspace_dir / "iteration-1"
    assert result["selected_eval_ids"] == [2]
    assert result["selected_eval_count"] == 1
    assert not (iteration_dir / "eval-1-please-analyze-this-decision-with-swot").exists()
    assert (iteration_dir / "eval-2-direct-result-mode-swot-please").exists()
