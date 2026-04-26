from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.analyzers.mechanism_analyzer import analyze_iteration, build_analysis_packet


def write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: SWOT Analysis",
                "description: Use this skill for SWOT decision support.",
                "---",
                "",
                "## Interaction Mode",
                "Support direct-result and staged modes.",
                "",
                "### Step 0:",
                "Check whether the user supplied enough information.",
                "",
                "### Step 1:",
                "Produce four quadrants and pause only when useful.",
                "",
                "## Output Format",
                "Strengths / Weaknesses / Opportunities / Threats / Strategy",
                "",
                "## Rules",
                "Do not ask repeated questions when information is sufficient.",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def _write_run(run_dir: Path, response: str, pass_rate: float, tokens: int) -> None:
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    output_file = run_dir / "outputs" / "final_response.md"
    output_file.write_text(response, encoding="utf-8")
    (run_dir / "grading.json").write_text(
        json.dumps(
            {
                "summary": {"pass_rate": pass_rate, "passed": 2, "failed": 0, "total": 2},
                "expectations": [],
                "execution_metrics": {"response_character_count": len(response), "errors_encountered": 0},
                "output_file": str(output_file),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "transcript.json").write_text(
        json.dumps({"assistant_response": response}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "request.json").write_text(
        json.dumps({"runner": "kimi-code", "messages": [{"role": "user", "content": "Give me SWOT."}]}, indent=2),
        encoding="utf-8",
    )
    (run_dir / "raw_response.json").write_text(json.dumps({"runner": "kimi-code"}, indent=2), encoding="utf-8")
    (run_dir / "timing.json").write_text(
        json.dumps({"total_duration_seconds": 1.0, "total_tokens": tokens}, indent=2),
        encoding="utf-8",
    )


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot-case"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot-case",
                "prompt": "Give me a direct SWOT result.",
                "expected_output": "Complete SWOT",
                "assertions": [
                    "The output includes strengths, weaknesses, opportunities, and threats.",
                    "The output respects direct-result mode.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    benchmark = {
        "metadata": {"skill_name": "SWOT Analysis", "skill_path": "/tmp/swot"},
        "runs": [
            {
                "eval_id": 1,
                "eval_name": "swot-case",
                "configuration": "with_skill",
                "run_number": 1,
                "result": {"pass_rate": 1.0, "passed": 2, "failed": 0, "total": 2, "time_seconds": 1.0, "tokens": 0, "tool_calls": 0, "errors": 0},
                "expectations": [],
                "notes": [],
            },
            {
                "eval_id": 1,
                "eval_name": "swot-case",
                "configuration": "without_skill",
                "run_number": 1,
                "result": {"pass_rate": 0.5, "passed": 1, "failed": 1, "total": 2, "time_seconds": 1.0, "tokens": 0, "tool_calls": 0, "errors": 0},
                "expectations": [],
                "notes": [],
            },
        ],
        "run_summary": {},
        "notes": [],
    }
    (iteration_dir / "benchmark.json").write_text(json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8")
    (iteration_dir / "level3-summary.json").write_text(
        json.dumps(
            {
                "primary_mode": "differential",
                "pairwise_summary": {
                    "win_rate": 1.0,
                    "tie_rate": 0.0,
                    "avg_margin": 0.7,
                    "judge_disagreement_rate": 0.0,
                    "cost_adjusted_value": 0.3,
                },
                "gate_summary": benchmark["run_summary"],
                "per_eval": [
                    {
                        "eval_id": 1,
                        "eval_name": "swot-case",
                        "run_number": 1,
                        "final_winner": "with_skill",
                        "avg_margin": 0.7,
                        "judge_disagreement": False,
                        "with_skill_run_dir": str(eval_dir / "with_skill" / "run-1"),
                        "without_skill_run_dir": str(eval_dir / "without_skill" / "run-1"),
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (iteration_dir / "stability.json").write_text(
        json.dumps({"overall": {"flags": []}, "per_eval": [{"eval_id": 1, "flags": []}]}, indent=2),
        encoding="utf-8",
    )

    _write_run(
        eval_dir / "with_skill" / "run-1",
        "## Strengths\n- clear\n## Weaknesses\n- budget\n## Opportunities\n- demand\n## Threats\n- competition\n## Strategy\n- validate first",
        1.0,
        0,
    )
    _write_run(eval_dir / "without_skill" / "run-1", "A decent but shallow answer.", 0.5, 0)
    return iteration_dir


def fake_sender(payload: dict) -> dict:
    content = json.dumps(
        {
            "per_eval": [
                {
                    "eval_id": 1,
                    "winner": "with_skill",
                    "mechanism_findings": ["The skill added a clearer decision structure."],
                    "instruction_use_signals": ["The skill preserved direct-result behavior."],
                    "failure_tags": ["skill-content.reasoning-shallow"],
                    "repair_layer": "skill-content",
                    "summary": "The skill improves structure but needs deeper reasoning.",
                }
            ],
            "cross_eval_summary": {"overall_winner": "with_skill", "key_patterns": ["better structure"]},
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
    return {"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 0}}


def test_build_analysis_packet_reads_level3_summary_and_run_records(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    packet = build_analysis_packet(iteration_dir, package_dir)

    assert packet["metadata"]["package_name"] == "swot-analysis"
    assert packet["level3_summary"]["primary_mode"] == "differential"
    assert packet["evals"][0]["with_skill_runs"][0]["pairwise_outcome"]["final_winner"] == "with_skill"


def test_analyze_iteration_writes_analysis_artifacts(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    result = analyze_iteration(
        iteration_dir,
        package_dir,
        sender=fake_sender,
        analyzer_model="kimi-for-coding",
    )

    assert result["analysis"]["metadata"]["analyzer_model"] == "kimi-for-coding"
    assert result["analysis"]["per_eval"][0]["repair_layer"] == "skill-content"
    assert (iteration_dir / "analysis.json").exists()
    assert (iteration_dir / "analysis.md").exists()
    assert (iteration_dir / "failure-tags.json").exists()


def test_analyze_iteration_default_kimi_path_reads_workspace_output_file(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    def fake_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, str | int]:
        output_path = cwd / "outputs" / "analysis.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "per_eval": [
                        {
                            "eval_id": 1,
                            "winner": "with_skill",
                            "mechanism_findings": ["The skill improves structure."],
                            "instruction_use_signals": ["Direct-result path held."],
                            "failure_tags": ["skill-content.reasoning-shallow"],
                            "repair_layer": "skill-content",
                            "summary": "Useful but shallow.",
                        }
                    ],
                    "cross_eval_summary": {"overall_winner": "with_skill"},
                    "repair_recommendations": [
                        {
                            "category": "skill-content.reasoning-shallow",
                            "repair_layer": "skill-content",
                            "action": "Add deeper reasoning.",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"returncode": 0, "stdout": json.dumps({"role": "assistant", "content": "done"}) + "\n", "stderr": ""}

    result = analyze_iteration(
        iteration_dir,
        package_dir,
        analyzer_model="kimi-for-coding",
        command_runner=fake_runner,
    )

    assert result["analysis"]["per_eval"][0]["winner"] == "with_skill"
    assert (iteration_dir / ".kimi-analysis" / "outputs" / "analysis.json").exists()
