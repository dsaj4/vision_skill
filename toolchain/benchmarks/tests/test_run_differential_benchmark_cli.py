from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.run_differential_benchmark import main


def test_main_prints_json_summary(monkeypatch, capsys, tmp_path: Path) -> None:
    expected = {
        "forward_judgments": [],
        "reversed_judgments": [],
        "consensus_pairs": [],
        "differential_benchmark": {
            "metadata": {
                "skill_name": "SWOT Analysis",
            },
            "summary": {
                "win_rate": 0.5,
            },
        },
    }

    def fake_run_differential_benchmark(iteration_dir: str | Path, **kwargs: object) -> dict:
        assert str(iteration_dir) == str(tmp_path / "iteration-1")
        assert kwargs["skill_name"] == "SWOT Analysis"
        assert kwargs["skill_path"] == "E:/pkg/swot-analysis"
        assert kwargs["judge_model"] == "qwen-judge-test"
        return expected

    monkeypatch.setattr(
        "toolchain.benchmarks.run_differential_benchmark.run_differential_benchmark",
        fake_run_differential_benchmark,
    )

    exit_code = main(
        [
            "--iteration-dir",
            str(tmp_path / "iteration-1"),
            "--skill-name",
            "SWOT Analysis",
            "--skill-path",
            "E:/pkg/swot-analysis",
            "--judge-model",
            "qwen-judge-test",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected
