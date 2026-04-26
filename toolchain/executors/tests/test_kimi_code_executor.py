from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.executors.kimi_code_executor import (
    build_messages,
    execute_iteration,
    execute_run,
)


def write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: swot-analysis",
                "description: Use this skill whenever the user needs SWOT decision support.",
                "---",
                "",
                "# SWOT Analysis",
                "Read the user's context and produce a direct SWOT result when information is sufficient.",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def write_iteration(base: Path, *, eval_metadata_extra: dict | None = None) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot"
    eval_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "eval_id": 1,
        "eval_name": "swot",
        "prompt": "Give me a direct SWOT result.",
        "expected_output": "Complete SWOT result",
        "files": [],
        "assertions": [],
    }
    metadata.update(eval_metadata_extra or {})
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for configuration in ("with_skill", "without_skill"):
        run_dir = eval_dir / configuration / "run-1" / "outputs"
        run_dir.mkdir(parents=True, exist_ok=True)
    return iteration_dir


def _json_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def fake_kimi_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, str | int]:
    output_path = cwd / "outputs" / "assistant.md"
    metadata_path = cwd / "outputs" / "run_metadata.json"
    conversation = json.loads((cwd / "inputs" / "conversation.json").read_text(encoding="utf-8"))
    turn_index = int(conversation["turn_index"])
    last_user = conversation["messages"][-1]["content"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with_skill = "--skills-dir" in args
    if with_skill:
        if turn_index == 1 and "继续" not in last_user:
            response = (
                "我先给第一步判断。回复\"继续\"我会展开策略。\n\n"
                "## Strengths\n- user insight\n"
                "## Weaknesses\n- limited budget\n"
            )
        elif "不对" in last_user:
            response = "已按你的修改意见重做：先聚焦低风险试水，再看是否扩大投入。"
        elif "直接" in last_user:
            response = "直接结论：先做小规模验证，不建议立刻扩大投入。"
        else:
            response = (
                "## Opportunities\n- market timing\n"
                "## Threats\n- competition\n"
                "## Strategy\n- validate demand first"
            )
        skill_dir = Path(args[args.index("--skills-dir") + 1])
        proxy_skill_path = skill_dir / "swot-analysis" / "SKILL.md"
        stdout = "\n".join(
            [
                _json_line(
                    {
                        "role": "assistant",
                        "content": "Finished writing workspace outputs.",
                        "tool_calls": [
                            {
                                "type": "function",
                                "id": "tc_proxy",
                                "function": {
                                    "name": "Read",
                                    "arguments": json.dumps({"file_path": str(proxy_skill_path)}),
                                },
                            }
                        ],
                    }
                ),
                _json_line(
                    {
                        "role": "tool",
                        "tool_call_id": "tc_proxy",
                        "content": proxy_skill_path.read_text(encoding="utf-8"),
                    }
                ),
            ]
        )
    else:
        response = f"Baseline turn {turn_index}: {last_user}"
        stdout = _json_line({"role": "assistant", "content": "Finished writing workspace outputs."})

    output_path.write_text(response, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "configuration": "with_skill" if with_skill else "without_skill",
                "turn_index": turn_index,
                "used_skill": with_skill,
                "last_user": last_user,
                "notes": "fake runner wrote controlled output files",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"returncode": 0, "stdout": stdout + "\n", "stderr": "To resume this session: kimi -r test-session\n"}


def test_build_messages_is_compatibility_only() -> None:
    with_skill = build_messages("User prompt", skill_text="# Skill")
    without_skill = build_messages("User prompt", skill_text=None)

    assert with_skill[0]["role"] == "system"
    assert "workspace skill proxy" in with_skill[0]["content"]
    assert without_skill == [{"role": "user", "content": "User prompt"}]


def test_execute_run_writes_artifacts_and_uses_kimi_code_host(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")
    run_dir = iteration_dir / "eval-1-swot" / "with_skill" / "run-1"

    result = execute_run(
        run_dir,
        package_dir,
        configuration="with_skill",
        command_runner=fake_kimi_runner,
        model="kimi-for-coding",
    )

    final_response = (run_dir / "outputs" / "final_response.md").read_text(encoding="utf-8")
    latest_response = (run_dir / "outputs" / "latest_assistant_response.md").read_text(encoding="utf-8")
    request_payload = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    transcript = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
    timing = json.loads((run_dir / "timing.json").read_text(encoding="utf-8"))

    assert "## Turn 1 User" in final_response
    assert "## Strengths" in final_response
    assert "## Strengths" in latest_response
    assert request_payload["runner"] == "kimi-code"
    assert request_payload["execution_mode"] == "workspace-file-task"
    assert request_payload["turn_script_source"] == "prompt"
    assert request_payload["final_response_mode"] == "full_conversation"
    assert request_payload["skill_mode"] == "workspace-file-task-proxy"
    assert transcript["provider"] == "kimi-code"
    assert transcript["turn_count"] == 1
    assert transcript["messages"][0]["role"] == "user"
    assert transcript["messages"][1]["role"] == "assistant"
    assert transcript["host_transcript"]["execution_mode"] == "workspace-file-task"
    assert transcript["latest_assistant_response"] == latest_response.strip()
    assert timing["token_source"] == "kimi-cli-unavailable"
    assert result["configuration"] == "with_skill"
    assert result["latest_output_file"].endswith("latest_assistant_response.md")
    assert (run_dir / "outputs" / "turns" / "turn-1-assistant.md").exists()


def test_execute_run_uses_execution_eval_turn_script_and_writes_full_conversation(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(
        tmp_path / "workspace",
        eval_metadata_extra={
            "execution_eval": {
                "enabled": True,
                "turn_script": [
                    {"label": "staged", "text": "先用 SWOT 帮我拆第一步。"},
                    {"label": "continue", "text": "继续"},
                    {"label": "direct-result", "text": "现在直接给结论。"},
                ],
            }
        },
    )
    run_dir = iteration_dir / "eval-1-swot" / "with_skill" / "run-1"

    execute_run(
        run_dir,
        package_dir,
        configuration="with_skill",
        command_runner=fake_kimi_runner,
        model="kimi-for-coding",
    )

    final_response = (run_dir / "outputs" / "final_response.md").read_text(encoding="utf-8")
    latest_response = (run_dir / "outputs" / "latest_assistant_response.md").read_text(encoding="utf-8")
    request_payload = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    transcript = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))

    assert request_payload["turn_script_source"] == "execution_eval.turn_script"
    assert request_payload["execution_eval"]["enabled"] is True
    assert "## Turn 1 User (staged)" in final_response
    assert "## Turn 2 User (continue)" in final_response
    assert "## Turn 3 User (direct-result)" in final_response
    assert "直接结论" in latest_response
    assert transcript["turn_count"] == 3
    assert len(transcript["messages"]) == 6
    assert transcript["host_transcript"]["turns"][1]["run_metadata"]["turn_index"] == 2
    assert (run_dir / "outputs" / "turns" / "turn-3-assistant.md").exists()


def test_execute_run_falls_back_to_host_eval_turn_script_for_legacy_cases(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(
        tmp_path / "workspace",
        eval_metadata_extra={
            "host_eval": {
                "enabled": True,
                "turn_script": [
                    {"label": "info-missing", "text": "我想转 AI 方向，但信息很乱。"},
                    {"label": "info-supply", "text": "目标是 6 个月内完成转型。"},
                ],
            }
        },
    )
    run_dir = iteration_dir / "eval-1-swot" / "with_skill" / "run-1"

    execute_run(
        run_dir,
        package_dir,
        configuration="with_skill",
        command_runner=fake_kimi_runner,
        model="kimi-for-coding",
    )

    request_payload = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    transcript = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))

    assert request_payload["turn_script_source"] == "host_eval.turn_script"
    assert transcript["turn_count"] == 2


def test_execute_iteration_runs_both_configurations(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")

    result = execute_iteration(
        iteration_dir,
        package_dir,
        command_runner=fake_kimi_runner,
        model="kimi-for-coding",
    )

    assert result["total_runs"] == 2
    assert (iteration_dir / "eval-1-swot" / "with_skill" / "run-1" / "raw_response.json").exists()
    assert (iteration_dir / "eval-1-swot" / "without_skill" / "run-1" / "outputs" / "final_response.md").exists()


def test_execute_iteration_skips_completed_runs_when_requested(tmp_path: Path) -> None:
    package_dir = write_package(tmp_path / "packages")
    iteration_dir = write_iteration(tmp_path / "workspace")
    completed_run_dir = iteration_dir / "eval-1-swot" / "with_skill" / "run-1"
    (completed_run_dir / "raw_response.json").write_text(json.dumps({"runner": "kimi-code"}), encoding="utf-8")
    (completed_run_dir / "transcript.json").write_text(json.dumps({"assistant_response": "done"}), encoding="utf-8")
    (completed_run_dir / "timing.json").write_text(json.dumps({"total_tokens": 0, "total_duration_seconds": 1.0}), encoding="utf-8")
    (completed_run_dir / "outputs" / "final_response.md").write_text("done", encoding="utf-8")
    (completed_run_dir / "outputs" / "latest_assistant_response.md").write_text("done", encoding="utf-8")

    result = execute_iteration(
        iteration_dir,
        package_dir,
        command_runner=fake_kimi_runner,
        model="kimi-for-coding",
        skip_completed=True,
    )

    assert result["total_runs"] == 2
    assert len(result["completed_runs"]) == 1
    assert len(result["skipped_runs"]) == 1
    assert result["skipped_runs"][0]["run_dir"] == str(completed_run_dir)
