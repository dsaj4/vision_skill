from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.judges.pairwise_judge import judge_pair


def write_run(run_dir: Path, response: str, pass_rate: float = 1.0, total_tokens: int = 1000) -> None:
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
    (run_dir / "grading.json").write_text(
        json.dumps(
            {
                "summary": {
                    "pass_rate": pass_rate,
                    "passed": 3,
                    "failed": 0,
                    "total": 3,
                },
                "execution_metrics": {
                    "response_character_count": len(response),
                    "errors_encountered": 0,
                },
                "output_file": str(run_dir / "outputs" / "final_response.md"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "timing.json").write_text(
        json.dumps(
            {
                "total_duration_seconds": 12.0,
                "total_tokens": total_tokens,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def fake_sender(payload: dict) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "winner": "A",
                            "margin": 0.6,
                            "confidence": 0.8,
                            "reasoning_summary": "Candidate A gives more useful tradeoff guidance.",
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
        "usage": {"prompt_tokens": 120, "completion_tokens": 180, "total_tokens": 300},
    }


def test_judge_pair_normalizes_forward_orientation_to_with_skill(tmp_path: Path) -> None:
    case_dir = tmp_path / "forward-orientation"
    with_skill_run = case_dir / "with_skill" / "run-1"
    without_skill_run = case_dir / "without_skill" / "run-1"
    write_run(with_skill_run, "## Strengths\n- clear judgment support")
    write_run(without_skill_run, "A decent answer without much tradeoff framing.")

    result = judge_pair(
        eval_id=1,
        eval_name="swot",
        prompt="Help me decide whether to launch a product.",
        run_number=1,
        with_skill_run_dir=with_skill_run,
        without_skill_run_dir=without_skill_run,
        orientation="forward",
        sender=fake_sender,
        judge_model="kimi-for-coding",
    )

    assert result["pair"]["candidate_a"]["configuration"] == "with_skill"
    assert result["judgment"]["winner"] == "A"
    assert result["judgment"]["normalized_winner"] == "with_skill"
    assert result["gate_check"]["comparable"] is True


def test_judge_pair_short_circuits_when_pair_is_not_comparable(tmp_path: Path) -> None:
    case_dir = tmp_path / "not-comparable"
    with_skill_run = case_dir / "with_skill" / "run-1"
    without_skill_run = case_dir / "without_skill" / "run-1"
    write_run(with_skill_run, "Useful answer.")
    write_run(without_skill_run, "")

    def should_not_be_called(payload: dict) -> dict:
        raise AssertionError("Sender should not be called for non-comparable pairs.")

    result = judge_pair(
        eval_id=1,
        eval_name="swot",
        prompt="Help me decide whether to launch a product.",
        run_number=1,
        with_skill_run_dir=with_skill_run,
        without_skill_run_dir=without_skill_run,
        orientation="forward",
        sender=should_not_be_called,
        judge_model="kimi-for-coding",
    )

    assert result["gate_check"]["comparable"] is False
    assert result["judgment"]["normalized_winner"] == "not_comparable"


def test_judge_pair_default_kimi_path_reads_workspace_output_file(tmp_path: Path) -> None:
    case_dir = tmp_path / "workspace-judge"
    with_skill_run = case_dir / "with_skill" / "run-1"
    without_skill_run = case_dir / "without_skill" / "run-1"
    write_run(with_skill_run, "A stronger answer with practical next steps.")
    write_run(without_skill_run, "A generic answer.")

    def fake_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, str | int]:
        output_path = cwd / "outputs" / "judgment.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "winner": "A",
                    "margin": 0.7,
                    "confidence": 0.9,
                    "reasoning_summary": "A is more actionable.",
                    "rubric_winner_by_dimension": {
                        "Thinking Support": "A",
                        "Tradeoff Quality": "A",
                        "Actionability": "A",
                        "Judgment Preservation": "tie",
                        "Boundary Safety": "tie",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"returncode": 0, "stdout": json.dumps({"role": "assistant", "content": "done"}) + "\n", "stderr": ""}

    result = judge_pair(
        eval_id=1,
        eval_name="swot",
        prompt="Help me decide whether to launch a product.",
        run_number=1,
        with_skill_run_dir=with_skill_run,
        without_skill_run_dir=without_skill_run,
        orientation="forward",
        command_runner=fake_runner,
        judge_model="kimi-for-coding",
    )

    assert result["judgment"]["normalized_winner"] == "with_skill"
    assert (case_dir / ".kimi-judge" / "run-1-forward" / "outputs" / "judgment.json").exists()
