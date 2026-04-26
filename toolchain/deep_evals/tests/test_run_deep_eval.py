from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.deep_evals.packet_builder import build_deep_eval_packet
from toolchain.deep_evals.run_deep_eval import run_deep_eval


def write_package(base: Path) -> Path:
    package_dir = base / "sample-package"
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "metadata" / "package.json").write_text(
        json.dumps({"package_name": "sample-package", "skill_name": "Sample Skill"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (package_dir / "metadata" / "quality-rubric.json").write_text(
        json.dumps(
            {
                "package_specific": [
                    {
                        "dimension": "Sample Fit",
                        "question": "Does the answer fit this sample package?",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (package_dir / "SKILL.md").write_text("# Sample Skill\n\nUse a direct, useful answer.", encoding="utf-8")
    return package_dir


def write_run(run_dir: Path, response: str) -> None:
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
    (run_dir / "outputs" / "latest_assistant_response.md").write_text(
        response.splitlines()[-1] if response.splitlines() else response,
        encoding="utf-8",
    )
    (run_dir / "request.json").write_text(json.dumps({"turns": ["Help me decide."]}), encoding="utf-8")
    (run_dir / "transcript.json").write_text(
        json.dumps({"assistant_response": response}, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "raw_response.json").write_text(json.dumps({"response": response}, ensure_ascii=False), encoding="utf-8")
    (run_dir / "timing.json").write_text(json.dumps({"total_duration_seconds": 1, "total_tokens": 10}), encoding="utf-8")
    (run_dir / "grading.json").write_text(
        json.dumps(
            {
                "summary": {"pass_rate": 1.0},
                "expectations": [],
                "output_file": str(run_dir / "outputs" / "final_response.md"),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-sample"
    eval_dir.mkdir(parents=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "sample",
                "prompt": "Help me decide.",
                "expected_output": "A useful decision answer.",
                "execution_eval": {
                    "enabled": True,
                    "turn_script": [
                        {"label": "staged", "text": "Help me decide."},
                        {"label": "continue", "text": "Continue."},
                    ],
                },
                "quality_rubric": [
                    {
                        "dimension": "Case Directness",
                        "question": "Does this case receive a direct answer?",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    write_run(eval_dir / "with_skill" / "run-1", "Use the option with the clearest tradeoff.")
    write_run(eval_dir / "without_skill" / "run-1", "You can think about pros and cons.")
    return iteration_dir


def fake_deep_eval_sender(payload: dict) -> dict:
    assert payload["messages"][1]["content"]
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "per_eval": [
                                {
                                    "eval_id": 1,
                                    "winner": "with_skill",
                                    "quality_score": 4,
                                    "dimension_assessments": [
                                        {
                                            "dimension": "Live Test Performance",
                                            "verdict": "strong",
                                            "evidence_refs": ["eval-1-sample/with_skill/run-1"],
                                        }
                                    ],
                                    "failed_dimensions": [],
                                    "comparative_judgment": "with_skill is more specific.",
                                    "quality_findings": ["It explains the tradeoff clearly."],
                                    "failure_tags": [],
                                    "repair_layer": "skill-content",
                                    "repair_hypothesis": "",
                                    "evidence_refs": ["eval-1-sample/with_skill/run-1"],
                                    "summary": "Overall improvement is clear.",
                                }
                            ],
                            "cross_eval_summary": {"overall": "skill quality improves"},
                            "repair_recommendations": ["Keep reducing template feel."],
                            "release_signal": {"decision": "pass", "confidence": 0.8, "reasons": ["quality improves"]},
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }


def test_build_deep_eval_packet_reads_raw_run_artifacts(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    packet = build_deep_eval_packet(iteration_dir, package_dir)

    assert packet["metadata"]["quality_primary_mode"] == "deep-quality"
    assert packet["rubric"]["schema_version"] == "darwin-conservative-v1"
    assert [item["dimension"] for item in packet["rubric"]["global"]] == ["Overall Structure", "Live Test Performance"]
    assert packet["rubric"]["package_specific"][0]["dimension"] == "Sample Fit"
    assert packet["evals"][0]["execution_eval"]["enabled"] is True
    assert packet["evals"][0]["quality_rubric"][0]["dimension"] == "Case Directness"
    assert packet["evals"][0]["runs"][0]["final_response"]
    assert packet["evals"][0]["runs"][0]["latest_assistant_response"]
    assert packet["evals"][0]["runs"][0]["evidence_paths"]["raw_response"].endswith("raw_response.json")
    assert packet["evals"][0]["runs"][0]["evidence_paths"]["latest_assistant_response"].endswith("latest_assistant_response.md")


def test_run_deep_eval_writes_quality_artifacts(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    result = run_deep_eval(
        iteration_dir,
        package_dir,
        sender=fake_deep_eval_sender,
        deep_eval_model="kimi-for-coding",
    )

    assert result["deep_eval"]["release_signal"]["decision"] == "pass"
    assert result["deep_eval"]["per_eval"][0]["dimension_assessments"][0]["dimension"] == "Live Test Performance"
    assert result["deep_eval"]["rubric"]["schema_version"] == "darwin-conservative-v1"
    assert (iteration_dir / "deep-eval.json").exists()
    assert (iteration_dir / "deep-eval.md").exists()
    assert (iteration_dir / "quality-failure-tags.json").exists()
