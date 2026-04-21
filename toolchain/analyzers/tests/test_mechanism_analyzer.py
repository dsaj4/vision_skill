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
                "name: SWOT 分析",
                "description: 使用 SWOT 结构分析决策。",
                "---",
                "",
                "## 交互模式",
                "分步执行；支持直接要结果。",
                "",
                "### Step 0:",
                "判断信息是否充分，不足时只追问缺失项。",
                "",
                "### Step 1:",
                "输出四象限并暂停确认。",
                "",
                "### Step 2:",
                "做优先级排序并暂停确认。",
                "",
                "### Step 3:",
                "给出交叉策略并暂停确认。",
                "",
                "## 输出格式",
                "输出 Strengths / Weaknesses / Opportunities / Threats / Strategy。",
                "",
                "## 规则",
                "信息充分时禁止重复提问；每步完成后必须暂停确认。",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot-case"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot-case",
                "prompt": "请直接给我 SWOT 结果。",
                "expected_output": "完整 SWOT",
                "assertions": [
                    "The output includes strengths, weaknesses, opportunities, and threats.",
                    "The output respects the user's direct-result request.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    benchmark = {
        "metadata": {"skill_name": "SWOT 分析", "skill_path": "/tmp/swot"},
        "runs": [
            {
                "eval_id": 1,
                "eval_name": "swot-case",
                "configuration": "with_skill",
                "run_number": 1,
                "result": {"pass_rate": 1.0, "passed": 2, "failed": 0, "total": 2, "time_seconds": 12.0, "tokens": 1000, "tool_calls": 0, "errors": 0},
                "expectations": [],
                "notes": [],
            },
            {
                "eval_id": 1,
                "eval_name": "swot-case",
                "configuration": "without_skill",
                "run_number": 1,
                "result": {"pass_rate": 0.5, "passed": 1, "failed": 1, "total": 2, "time_seconds": 8.0, "tokens": 600, "tool_calls": 0, "errors": 0},
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
                        "with_skill_run_dir": str(iteration_dir / "eval-1-swot-case" / "with_skill" / "run-1"),
                        "without_skill_run_dir": str(iteration_dir / "eval-1-swot-case" / "without_skill" / "run-1"),
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    stability = {
        "metadata": {"runs_per_configuration": 3},
        "per_eval": [
            {
                "eval_id": 1,
                "eval_name": "swot-case",
                "flags": ["weak_stability_value"],
                "configurations": {
                    "with_skill": {"expectation_variance": {}, "drift": {"drift_detected": False}},
                    "without_skill": {"expectation_variance": {}, "drift": {"drift_detected": False}},
                },
            }
        ],
        "overall": {"flags": ["weak_stability_value"]},
        "variance_by_expectation": {"expectations": []},
    }
    (iteration_dir / "stability.json").write_text(json.dumps(stability, ensure_ascii=False, indent=2), encoding="utf-8")

    taxonomy = {
        "categories": [
            {"id": "source", "subcategories": [{"id": "source.missing-context"}]},
            {"id": "blueprint-spec", "subcategories": [{"id": "blueprint-spec.eval-gap"}]},
            {"id": "template", "subcategories": [{"id": "template.voice-drift"}]},
            {"id": "skill-content", "subcategories": [{"id": "skill-content.reasoning-shallow"}]},
        ]
    }

    for configuration, pass_rate in (("with_skill", 1.0), ("without_skill", 0.5)):
        run_dir = eval_dir / configuration / "run-1"
        (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
        response = (
            "## Strengths\n- insight\n## Weaknesses\n- budget\n## Opportunities\n- demand\n## Threats\n- competitors\n## Strategy\n- validate quickly"
            if configuration == "with_skill"
            else "可以尝试这个方向，但需要先看清竞争。"
        )
        (run_dir / "outputs" / "final_response.md").write_text(response, encoding="utf-8")
        (run_dir / "request.json").write_text(
            json.dumps({"model": "qwen-test", "messages": [{"role": "user", "content": "请直接给我 SWOT 结果。"}]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "transcript.json").write_text(
            json.dumps(
                {
                    "configuration": configuration,
                    "messages": [{"role": "user", "content": "请直接给我 SWOT 结果。"}],
                    "assistant_response": response,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (run_dir / "raw_response.json").write_text(
            json.dumps({"choices": [{"message": {"content": response}}], "usage": {"total_tokens": 1000}}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "timing.json").write_text(
            json.dumps({"total_tokens": 1000 if configuration == "with_skill" else 600, "total_duration_seconds": 12.0 if configuration == "with_skill" else 8.0}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (run_dir / "grading.json").write_text(
            json.dumps(
                {
                    "eval_id": 1,
                    "eval_name": "swot-case",
                    "prompt": "请直接给我 SWOT 结果。",
                    "output_file": str(run_dir / "outputs" / "final_response.md"),
                    "expectations": [
                        {"id": "swot-quadrants", "text": "quadrants", "passed": True, "evidence": "ok"},
                        {"id": "direct-result-mode", "text": "direct", "passed": configuration == "with_skill", "evidence": "ok"},
                    ],
                    "summary": {"passed": 2 if configuration == "with_skill" else 1, "failed": 0 if configuration == "with_skill" else 1, "total": 2, "pass_rate": pass_rate},
                    "execution_metrics": {"total_tool_calls": 0, "errors_encountered": 0},
                    "timing": {"total_duration_seconds": 12.0 if configuration == "with_skill" else 8.0},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return iteration_dir, taxonomy


def fake_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    content = json.dumps(
        {
            "per_eval": [
                {
                    "eval_id": 1,
                    "winner": "with_skill",
                    "mechanism_findings": ["with_skill maintained SWOT structure and explicit strategy output"],
                    "instruction_use_signals": ["skill instructions clearly shaped the output format"],
                    "failure_tags": ["skill-content.reasoning-shallow"],
                    "repair_layer": "skill-content",
                    "summary": "with_skill produced the intended structure, but still needs deeper reasoning.",
                }
            ],
            "cross_eval_summary": {
                "overall_winner": "with_skill",
                "key_patterns": ["structure improved with the skill"],
                "critical_risks": ["reasoning depth remains limited"],
            },
            "repair_recommendations": ["Strengthen the strategy reasoning examples inside the package."],
        },
        ensure_ascii=False,
        indent=2,
    )
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 200, "completion_tokens": 150, "total_tokens": 350},
    }


def test_build_analysis_packet_extracts_skill_sections_and_run_signals(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir, taxonomy = write_iteration(tmp_path / "workspace")

    packet = build_analysis_packet(iteration_dir, package_dir, taxonomy)

    assert packet["skill_mechanisms"]["interaction_mode"]
    assert packet["skill_mechanisms"]["step_0"]
    assert packet["evals"][0]["with_skill_runs"][0]["mechanism_signals"]["has_structured_output"] is True
    assert packet["evals"][0]["without_skill_runs"][0]["mechanism_signals"]["has_structured_output"] is False


def test_analyze_iteration_writes_analysis_and_failure_tags(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir, taxonomy = write_iteration(tmp_path / "workspace")

    result = analyze_iteration(
        iteration_dir,
        package_dir,
        taxonomy=taxonomy,
        sender=fake_sender,
        api_key="test-key",
        analyzer_model="qwen-analyzer-test",
    )

    assert result["analysis"]["metadata"]["analyzer_model"] == "qwen-analyzer-test"
    assert result["analysis"]["per_eval"][0]["repair_layer"] == "skill-content"
    assert (iteration_dir / "analysis.json").exists()
    assert (iteration_dir / "analysis.md").exists()
    assert (iteration_dir / "failure-tags.json").exists()


def sparse_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    content = json.dumps(
        {
            "per_eval": [
                {"eval_id": 1}
            ],
            "cross_eval_summary": {
                "overall_skill_value": "negative",
                "critical_issue": "Skill adds overhead without improving pass rate.",
            },
            "repair_recommendations": [
                {
                    "repair_layer": "blueprint-spec",
                    "issue_id": "blueprint-spec.eval-gap",
                    "issue": "Eval expectations are misaligned.",
                    "action": "Tighten eval design.",
                }
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 200, "completion_tokens": 150, "total_tokens": 350},
    }


def test_analyze_iteration_recovers_failure_tags_from_repair_recommendations(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir, taxonomy = write_iteration(tmp_path / "workspace")

    result = analyze_iteration(
        iteration_dir,
        package_dir,
        taxonomy=taxonomy,
        sender=sparse_sender,
        api_key="test-key",
        analyzer_model="qwen-analyzer-test",
    )

    assert result["analysis"]["per_eval"][0]["failure_tags"] == ["blueprint-spec.eval-gap"]
    assert result["analysis"]["per_eval"][0]["repair_layer"] == "blueprint-spec"
    assert result["analysis"]["failure_tag_counts"]["blueprint-spec.eval-gap"] == 1


def malformed_cross_eval_sender(payload: dict, endpoint: str, api_key: str, timeout_seconds: int) -> dict:
    content = json.dumps(
        {
            "per_eval": [
                {
                    "eval_id": 1,
                    "winner": "with_skill",
                }
            ],
            "cross_eval_summary": "Skill improved structure, but the summary was returned as plain text.",
            "repair_recommendations": [],
        },
        ensure_ascii=False,
        indent=2,
    )
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
    }


def test_analyze_iteration_tolerates_string_cross_eval_summary(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir, taxonomy = write_iteration(tmp_path / "workspace")

    result = analyze_iteration(
        iteration_dir,
        package_dir,
        taxonomy=taxonomy,
        sender=malformed_cross_eval_sender,
        api_key="test-key",
        analyzer_model="qwen-analyzer-test",
    )

    assert result["analysis"]["cross_eval_summary"]["critical_issue"] == "Skill improved structure, but the summary was returned as plain text."
    assert result["analysis"]["per_eval"][0]["winner"] == "with_skill"


def test_build_analysis_packet_includes_level3_pairwise_signals(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir, taxonomy = write_iteration(tmp_path / "workspace")

    packet = build_analysis_packet(iteration_dir, package_dir, taxonomy)

    assert packet["level3_summary"]["primary_mode"] == "differential"
    assert packet["evals"][0]["with_skill_runs"][0]["pairwise_outcome"]["final_winner"] == "with_skill"
