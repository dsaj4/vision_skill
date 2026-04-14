from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.eval_factory.sync import resolve_package_evals, sync_package_evals


def write_factory(root: Path) -> Path:
    factory_dir = root / "eval-factory"
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
                "host_eval": {
                    "enabled": True,
                    "turn_script": [{"text": "Please run the host path."}],
                    "expected_trigger": True,
                    "expected_trigger_signals": ["proxy_skill_read"],
                    "expected_protocol_path": "direct-result -> no-checkpoint",
                },
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
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return bundle_path


def write_package(root: Path, bundle_path: Path) -> Path:
    package_dir = root / "package"
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "evals").mkdir(parents=True)
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
                "skill_name": "Sample Skill",
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
    return package_dir


def test_sync_package_evals_exports_configured_certified_bundle(tmp_path: Path) -> None:
    bundle_path = write_factory(tmp_path)
    package_dir = write_package(tmp_path, bundle_path)

    result = sync_package_evals(package_dir)
    exported = json.loads((package_dir / "evals" / "evals.json").read_text(encoding="utf-8"))
    metadata = json.loads((package_dir / "evals" / "eval-sync.json").read_text(encoding="utf-8"))

    assert result["synced"] is True
    assert result["bundle_id"] == "bundle-v0.1"
    assert exported["bundle_id"] == "bundle-v0.1"
    assert exported["evals"][0]["id"] == 101
    assert exported["evals"][0]["host_eval"]["enabled"] is True
    assert metadata["bundle_id"] == "bundle-v0.1"


def test_resolve_package_evals_auto_syncs_before_returning(tmp_path: Path) -> None:
    bundle_path = write_factory(tmp_path)
    package_dir = write_package(tmp_path, bundle_path)

    resolved = resolve_package_evals(package_dir)

    assert resolved["source_mode"] == "certified-bundle"
    assert resolved["data"]["evals"][0]["id"] == 101


def test_resolve_package_evals_falls_back_to_package_local_when_no_eval_source(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "evals").mkdir(parents=True)
    (package_dir / "metadata" / "package.json").write_text(
        json.dumps(
            {
                "package_name": "local-package",
                "skill_name": "Local Skill",
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
                "skill_name": "Local Skill",
                "evals": [
                    {
                        "id": 1,
                        "prompt": "local prompt",
                        "expected_output": "local output",
                        "files": [],
                        "expectations": ["local expectation"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    resolved = resolve_package_evals(package_dir)

    assert resolved["source_mode"] == "package-local"
    assert resolved["data"]["evals"][0]["id"] == 1
