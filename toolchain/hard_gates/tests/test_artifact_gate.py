from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.hard_gates.artifact_gate import run_hard_gate


def write_run(run_dir: Path, response: str = "answer") -> None:
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "request.json").write_text("{}", encoding="utf-8")
    (run_dir / "raw_response.json").write_text("{}", encoding="utf-8")
    (run_dir / "transcript.json").write_text("{}", encoding="utf-8")
    (run_dir / "timing.json").write_text(json.dumps({"total_duration_seconds": 1}), encoding="utf-8")
    (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
    (run_dir / "outputs" / "latest_assistant_response.md").write_text(response, encoding="utf-8")


def test_run_hard_gate_writes_passed_report(tmp_path: Path) -> None:
    eval_dir = tmp_path / "iteration-1" / "eval-1-sample"
    eval_dir.mkdir(parents=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps({"eval_id": 1, "eval_name": "sample"}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_run(eval_dir / "with_skill" / "run-1")
    write_run(eval_dir / "without_skill" / "run-1")

    report = run_hard_gate(tmp_path / "iteration-1")

    assert report["passed"] is True
    assert report["metadata"]["gate_type"] == "readiness-only"
    assert report["metadata"]["eval_count"] == 1
    assert report["metadata"]["run_count"] == 2
    assert (tmp_path / "iteration-1" / "hard-gate.json").exists()
    assert (tmp_path / "iteration-1" / "hard-gate.md").exists()


def test_run_hard_gate_marks_missing_and_empty_response(tmp_path: Path) -> None:
    eval_dir = tmp_path / "iteration-1" / "eval-1-sample"
    eval_dir.mkdir(parents=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps({"eval_id": 1, "eval_name": "sample"}, ensure_ascii=False),
        encoding="utf-8",
    )
    run_dir = eval_dir / "with_skill" / "run-1"
    write_run(run_dir, response="")
    (run_dir / "raw_response.json").unlink()

    report = run_hard_gate(tmp_path / "iteration-1")

    assert report["passed"] is False
    assert "empty_final_response" in report["blockers"]
    assert "missing:raw_response.json" in report["blockers"]


def test_run_hard_gate_requires_both_skill_and_baseline_runs(tmp_path: Path) -> None:
    eval_dir = tmp_path / "iteration-1" / "eval-1-sample"
    eval_dir.mkdir(parents=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps({"eval_id": 1, "eval_name": "sample"}, ensure_ascii=False),
        encoding="utf-8",
    )
    write_run(eval_dir / "with_skill" / "run-1")

    report = run_hard_gate(tmp_path / "iteration-1")

    assert report["passed"] is False
    assert "missing_configuration:without_skill" in report["blockers"]
    assert report["per_eval"][0]["passed"] is False
