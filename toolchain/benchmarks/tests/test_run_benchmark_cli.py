from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.run_benchmark import main


def test_main_prints_json_summary(monkeypatch, capsys, tmp_path: Path) -> None:
    expected = {
        "iteration_dir": str(tmp_path / "iteration-1"),
        "graded_runs": [],
        "benchmark": {"metadata": {"skill_name": "SWOT Analysis"}},
        "benchmark_path": str(tmp_path / "iteration-1" / "benchmark.json"),
        "benchmark_markdown_path": str(tmp_path / "iteration-1" / "benchmark.md"),
    }

    def fake_grade_iteration_runs(iteration_path: str | Path, skill_name: str = "", skill_path: str = "") -> dict:
        assert str(iteration_path) == expected["iteration_dir"]
        assert skill_name == "SWOT Analysis"
        assert skill_path == "E:/pkg/swot-analysis"
        return expected

    monkeypatch.setattr("toolchain.benchmarks.run_benchmark.grade_iteration_runs", fake_grade_iteration_runs)

    exit_code = main(
        [
            "--iteration-dir",
            expected["iteration_dir"],
            "--skill-name",
            "SWOT Analysis",
            "--skill-path",
            "E:/pkg/swot-analysis",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected
