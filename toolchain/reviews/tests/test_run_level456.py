from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.benchmarks.run_benchmark import grade_iteration_runs
from toolchain.run_level456 import main, run_level456


def write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    (package_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: SWOT Analysis",
                "description: Help the user analyze a decision with SWOT.",
                "---",
                "",
                "## 交互模式",
                "Support staged interaction and direct-result mode.",
                "",
                "### Step 0:",
                "Ask only for missing information when necessary.",
                "",
                "### Step 1:",
                "Draft the four quadrants and pause for confirmation.",
                "",
                "### Step 2:",
                "Prioritize insights and pause for confirmation.",
                "",
                "### Step 3:",
                "Propose cross-quadrant strategy and pause for confirmation.",
                "",
                "## 输出格式",
                "Output Strengths / Weaknesses / Opportunities / Threats / Strategy.",
                "",
                "## 规则",
                "Do not repeat questions when information is sufficient.",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot",
                "prompt": "Give me a direct SWOT result for an AI note-taking app.",
                "expected_output": "A full SWOT with strategy guidance.",
                "assertions": [
                    {
                        "id": "all-quadrants",
                        "type": "contains_all",
                        "keywords": ["strengths", "weaknesses", "opportunities", "threats"],
                        "text": "Must include all four SWOT quadrants.",
                    },
                    {
                        "id": "strategy-guidance",
                        "type": "contains_any",
                        "keywords": ["strategy", "actions"],
                        "text": "Must include strategy guidance.",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with_skill_responses = [
        "## Strengths\n- fast capture\n## Weaknesses\n- limited budget\n## Opportunities\n- team demand\n## Threats\n- incumbents\n## Strategy\n- validate niche first",
        "## Strengths\n- fast capture\n## Weaknesses\n- limited budget\n## Opportunities\n- team demand\n## Threats\n- incumbents\n## Strategy\n- validate niche first",
        "## Strengths\n- fast capture\n## Weaknesses\n- limited budget\n## Opportunities\n- team demand\n## Threats\n- incumbents",
    ]
    without_skill_responses = [
        "## Strengths\n- fast capture\n## Weaknesses\n- limited budget\n## Opportunities\n- team demand\n## Threats\n- incumbents",
        "## Strengths\n- fast capture\n## Weaknesses\n- limited budget\n## Opportunities\n- team demand\n## Threats\n- incumbents",
        "## Strengths\n- fast capture\n## Weaknesses\n- limited budget\n## Opportunities\n- team demand\n## Threats\n- incumbents",
    ]

    for configuration, responses in (("with_skill", with_skill_responses), ("without_skill", without_skill_responses)):
        for index, response in enumerate(responses, start=1):
            run_dir = eval_dir / configuration / f"run-{index}"
            (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
            (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
            (run_dir / "request.json").write_text(
                json.dumps({"model": "qwen-test", "messages": [{"role": "user", "content": "Give me the SWOT result."}]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (run_dir / "transcript.json").write_text(
                json.dumps(
                    {
                        "configuration": configuration,
                        "messages": [{"role": "user", "content": "Give me the SWOT result."}],
                        "assistant_response": response,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            (run_dir / "raw_response.json").write_text(
                json.dumps({"choices": [{"message": {"content": response}}], "usage": {"total_tokens": 800}}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (run_dir / "timing.json").write_text(
                json.dumps(
                    {
                        "total_tokens": 950 if configuration == "with_skill" else 700,
                        "total_duration_seconds": 10.0 + index,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    return iteration_dir


def fake_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "per_eval": [
                                {
                                    "eval_id": 1,
                                    "winner": "tie",
                                    "mechanism_findings": ["The skill improved structure but not value."],
                                    "instruction_use_signals": ["The skill shaped the SWOT sections."],
                                    "failure_tags": ["blueprint-spec.protocol-gap"],
                                    "repair_layer": "blueprint-spec",
                                    "summary": "Staged protocol still creates incomplete direct-result behavior.",
                                }
                            ],
                            "cross_eval_summary": {
                                "overall_winner": "tie",
                                "key_patterns": ["structure improved", "value remained flat"],
                                "critical_risks": ["protocol drift persists"],
                            },
                            "repair_recommendations": [
                                {
                                    "category": "blueprint-spec.protocol-gap",
                                    "repair_layer": "blueprint-spec",
                                    "action": "Tighten the direct-result contract in the blueprint.",
                                }
                            ],
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 120, "total_tokens": 220},
    }


def prepare_benchmarked_iteration(tmp_path: Path) -> tuple[Path, Path]:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")
    grade_iteration_runs(iteration_dir, skill_name="SWOT Analysis", skill_path=str(package_dir))
    return package_dir, iteration_dir


def test_run_level456_writes_artifacts_and_preserves_existing_review(tmp_path: Path) -> None:
    package_dir, iteration_dir = prepare_benchmarked_iteration(tmp_path)
    existing_review = {
        "reviewer": "Alice",
        "reviewed_at": "2026-04-08T10:00:00Z",
        "package_name": package_dir.name,
        "iteration": iteration_dir.name,
        "scores": {
            "Protocol Fidelity": 2,
            "Structural Output": 2,
            "Thinking Support": 2,
            "Judgment Preservation": 2,
            "Boundary Safety": 2,
            "VisionTree Voice": 2,
        },
        "decision": "pass",
        "notes": "Keep moving.",
    }
    (iteration_dir / "human-review-score.json").write_text(
        json.dumps(existing_review, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = run_level456(
        iteration_dir,
        package_dir,
        sender=fake_sender,
        api_key="test-key",
        analyzer_model="qwen-analyzer-test",
    )

    review = json.loads((iteration_dir / "human-review-score.json").read_text(encoding="utf-8"))
    assert (iteration_dir / "stability.json").exists()
    assert (iteration_dir / "analysis.json").exists()
    assert (iteration_dir / "human-review-packet.md").exists()
    assert (iteration_dir / "release-recommendation.json").exists()
    assert review["reviewer"] == "Alice"
    assert review["decision"] == "pass"
    assert result["analysis_model"] == "qwen-analyzer-test"


def test_main_prints_json_summary(monkeypatch, capsys, tmp_path: Path) -> None:
    expected = {
        "iteration_dir": str(tmp_path / "iteration-1"),
        "package_dir": str(tmp_path / "swot-analysis"),
        "analysis_model": "qwen-analyzer-test",
    }

    def fake_run_level456(iteration_dir: Path, package_dir: Path, **kwargs: object) -> dict:
        assert str(iteration_dir) == expected["iteration_dir"]
        assert str(package_dir) == expected["package_dir"]
        return expected

    monkeypatch.setattr("toolchain.run_level456.run_level456", fake_run_level456)

    exit_code = main(
        [
            "--iteration-dir",
            expected["iteration_dir"],
            "--package-dir",
            expected["package_dir"],
            "--analyzer-model",
            "qwen-analyzer-test",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected
