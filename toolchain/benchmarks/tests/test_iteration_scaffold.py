from __future__ import annotations

import json
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
