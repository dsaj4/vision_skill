from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.agent_hosts.kimi_code_host import KimiCodeHost


def _write_package(base: Path) -> Path:
    package_dir = base / "swot-analysis"
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: swot-analysis",
                "description: Use this skill whenever the user needs a SWOT analysis for a decision.",
                "---",
                "",
                "# SWOT Analysis",
                "",
                "Read the user's context and produce either a follow-up or a full SWOT result.",
            ]
        ),
        encoding="utf-8",
    )
    return package_dir


def _json_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def test_kimi_code_host_prepares_proxy_skill_and_parses_stream_json(tmp_path: Path) -> None:
    package_dir = _write_package(tmp_path / "packages")
    recorded_commands: list[list[str]] = []

    def fake_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, str | int]:
        recorded_commands.append(args)
        proxy_skill_path = cwd / ".kimi" / "skills" / "swot-analysis" / "SKILL.md"
        canonical_skill_path = package_dir / "SKILL.md"
        if len(recorded_commands) == 1:
            stdout = "\n".join(
                [
                    _json_line(
                        {
                            "role": "assistant",
                            "content": "I will inspect the local skill before answering.",
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
                    _json_line(
                        {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "id": "tc_canonical",
                                    "function": {
                                        "name": "Read",
                                        "arguments": json.dumps({"file_path": str(canonical_skill_path)}),
                                    },
                                }
                            ],
                        }
                    ),
                    _json_line(
                        {
                            "role": "tool",
                            "tool_call_id": "tc_canonical",
                            "content": canonical_skill_path.read_text(encoding="utf-8"),
                        }
                    ),
                    _json_line(
                        {
                            "role": "assistant",
                            "content": "Before I can continue, I need your target role and available time.",
                        }
                    ),
                ]
            )
            return {"returncode": 0, "stdout": stdout, "stderr": "To resume this session: kimi -r kimi-session-102\n"}

        stdout = _json_line(
            {
                "role": "assistant",
                "content": (
                    "## Strengths\n- domain context\n"
                    "## Weaknesses\n- limited technical depth\n"
                    "## Opportunities\n- AI operator roles are growing\n"
                    "## Threats\n- competition is rising\n"
                    "## Strategy\n- start with a low-risk test path"
                ),
            }
        )
        return {"returncode": 0, "stdout": stdout, "stderr": ""}

    host = KimiCodeHost(session_root=tmp_path / "host-session", command_runner=fake_runner, model="kimi-for-coding")
    session = host.prepare_session(package_dir, {"id": 102, "prompt": "Help me decide whether to pivot."})

    proxy_skill = Path(session["proxy_skill_path"])
    assert proxy_skill.exists()
    assert str(package_dir.resolve() / "SKILL.md") in proxy_skill.read_text(encoding="utf-8")

    first_turn = host.send_user_turn(session, "I want to pivot into AI work, but the context is still messy.")
    second_turn = host.send_user_turn(session, "My target is to switch within 6 months and I have 8 hours a week.")
    transcript = host.read_transcript(session)
    trigger_report = host.detect_skill_trigger(transcript, "swot-analysis")

    assert first_turn["thread_id"] == "kimi-session-102"
    assert second_turn["thread_id"] == "kimi-session-102"
    assert transcript["host_backend"] == "kimi-code"
    assert len(transcript["turns"]) == 2
    assert transcript["turns"][-1]["assistant_text"].startswith("## Strengths")
    assert recorded_commands[0][0:3] == ["kimi", "--print", "--output-format=stream-json"]
    assert "--work-dir" in recorded_commands[0]
    assert "--add-dir" in recorded_commands[0]
    assert "--skills-dir" in recorded_commands[0]
    assert "--session" not in recorded_commands[0]
    assert "--model" in recorded_commands[0]
    assert recorded_commands[0][-2] == "--prompt"
    assert recorded_commands[1][recorded_commands[1].index("--session") + 1] == "kimi-session-102"
    assert trigger_report["triggered"] is True
    assert trigger_report["skill_read_before_first_answer"] is True
    assert trigger_report["observed_trigger_signals"]["proxy_skill_read"] is True
    assert trigger_report["observed_trigger_signals"]["canonical_skill_read"] is True
    assert any(item["type"] == "proxy_skill_read" for item in trigger_report["evidence"])


def test_kimi_code_host_falls_back_to_plain_text_output(tmp_path: Path) -> None:
    package_dir = _write_package(tmp_path / "packages")

    def fake_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, str | int]:
        return {"returncode": 0, "stdout": "Plain final answer from Kimi Code.", "stderr": ""}

    host = KimiCodeHost(session_root=tmp_path / "host-session", command_runner=fake_runner)
    session = host.prepare_session(package_dir, {"id": 1})
    response = host.send_user_turn(session, "Give a direct answer.")

    assert response["assistant_text"] == "Plain final answer from Kimi Code."
    assert session["turns"][0]["warnings"] == ["Plain final answer from Kimi Code."]
