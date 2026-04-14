from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.agent_hosts.codex_host import CodexHost


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


def test_codex_host_prepares_proxy_skill_and_supports_multi_turn_resume(tmp_path: Path) -> None:
    package_dir = _write_package(tmp_path / "packages")
    recorded_commands: list[list[str]] = []

    def fake_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, str | int]:
        recorded_commands.append(args)
        if len(recorded_commands) == 1:
            proxy_skill_path = cwd / ".codex" / "skills" / "swot-analysis" / "SKILL.md"
            stdout = "\n".join(
                [
                    _json_line({"type": "thread.started", "thread_id": "thread-1"}),
                    _json_line({"type": "turn.started"}),
                    _json_line(
                        {
                            "type": "item.completed",
                            "item": {
                                "id": "item_0",
                                "type": "command_execution",
                                "command": f"Get-Content -Raw '{proxy_skill_path.as_posix()}'",
                                "aggregated_output": proxy_skill_path.read_text(encoding="utf-8"),
                                "status": "completed",
                            },
                        }
                    ),
                    _json_line(
                        {
                            "type": "item.completed",
                            "item": {
                                "id": "item_1",
                                "type": "command_execution",
                                "command": f"Get-Content -Raw '{(package_dir / 'SKILL.md').as_posix()}'",
                                "aggregated_output": (package_dir / "SKILL.md").read_text(encoding="utf-8"),
                                "status": "completed",
                            },
                        }
                    ),
                    _json_line(
                        {
                            "type": "item.completed",
                            "item": {
                                "id": "item_2",
                                "type": "agent_message",
                                "text": "还缺目标和当前资源两个关键信息。你先补这两项，我再继续。",
                            },
                        }
                    ),
                    _json_line({"type": "turn.completed"}),
                ]
            )
            return {"returncode": 0, "stdout": stdout, "stderr": ""}

        stdout = "\n".join(
            [
                _json_line({"type": "turn.started"}),
                _json_line(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item_3",
                            "type": "agent_message",
                            "text": "## Strengths\n- 内容运营经验\n## Weaknesses\n- 技术深度不足\n## Opportunities\n- AI 产品运营需求上升\n## Threats\n- 学习曲线陡峭\n## Strategy\n- 先做低风险试水，再决定是否转岗",
                        },
                    }
                ),
                _json_line({"type": "turn.completed"}),
            ]
        )
        return {"returncode": 0, "stdout": stdout, "stderr": ""}

    host = CodexHost(session_root=tmp_path / "host-session", command_runner=fake_runner)
    session = host.prepare_session(package_dir, {"id": 102, "prompt": "请帮我判断是否转岗"})

    proxy_skill = Path(session["proxy_skill_path"])
    assert proxy_skill.exists()
    assert str(package_dir / "SKILL.md") in proxy_skill.read_text(encoding="utf-8")

    first_turn = host.send_user_turn(session, "我想转去 AI 方向，但现在信息很乱。")
    second_turn = host.send_user_turn(session, "目标是 6 个月内找到 AI 产品运营机会，现在每周能投入 8 小时学习。")
    transcript = host.read_transcript(session)
    trigger_report = host.detect_skill_trigger(transcript, "swot-analysis")

    assert first_turn["thread_id"] == "thread-1"
    assert second_turn["thread_id"] == "thread-1"
    assert transcript["thread_id"] == "thread-1"
    assert len(transcript["turns"]) == 2
    assert transcript["turns"][-1]["assistant_text"].startswith("## Strengths")
    assert recorded_commands[0][:3] == ["codex", "exec", "--json"]
    assert recorded_commands[1][:6] == ["codex", "exec", "--skip-git-repo-check", "-C", str(Path(session["session_dir"])), "resume"]
    assert "thread-1" in recorded_commands[1]
    assert trigger_report["triggered"] is True
    assert trigger_report["skill_read_before_first_answer"] is True
    assert trigger_report["first_skill_read_turn_index"] == 1
    assert trigger_report["first_answer_turn_index"] == 1
    assert trigger_report["observed_trigger_signals"]["proxy_skill_read"] is True
    assert any(item["type"] == "proxy_skill_read" for item in trigger_report["evidence"])
