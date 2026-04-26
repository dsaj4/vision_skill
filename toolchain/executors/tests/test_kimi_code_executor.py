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


def write_iteration(base: Path) -> Path:
    iteration_dir = base / "iteration-1"
    eval_dir = iteration_dir / "eval-1-swot"
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": 1,
                "eval_name": "swot",
                "prompt": "Give me a direct SWOT result.",
                "expected_output": "Complete SWOT result",
                "files": [],
                "assertions": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with_skill = "--skills-dir" in args
    if with_skill:
        response = (
            "## Strengths\n- user insight\n"
            "## Weaknesses\n- limited budget\n"
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
        response = "A baseline answer without full SWOT structure."
        stdout = _json_line({"role": "assistant", "content": "Finished writing workspace outputs."})

    output_path.write_text(response, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "configuration": "with_skill" if with_skill else "without_skill",
                "turn_index": 1,
                "used_skill": with_skill,
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
    request_payload = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    transcript = json.loads((run_dir / "transcript.json").read_text(encoding="utf-8"))
    timing = json.loads((run_dir / "timing.json").read_text(encoding="utf-8"))

    assert "## Strengths" in final_response
    assert request_payload["runner"] == "kimi-code"
    assert request_payload["execution_mode"] == "workspace-file-task"
    assert request_payload["skill_mode"] == "workspace-file-task-proxy"
    assert transcript["provider"] == "kimi-code"
    assert transcript["host_transcript"]["execution_mode"] == "workspace-file-task"
    assert timing["token_source"] == "kimi-cli-unavailable"
    assert result["configuration"] == "with_skill"


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
