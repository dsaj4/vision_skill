from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from toolchain.agent_hosts.host_utils import CommandRunner, extract_frontmatter, read_text, render_proxy_skill
from toolchain.agent_hosts.event_normalizer import normalize_host_transcript
from toolchain.agent_hosts.signal_extractor import extract_host_signals
from toolchain.kimi_runtime import (
    build_kimi_args,
    content_to_text,
    default_kimi_command_runner,
    extract_resume_session_id,
    parse_jsonl,
)


def _parse_tool_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"raw_arguments": value}
    return parsed if isinstance(parsed, dict) else {"raw_arguments": value}


def _tool_call_command(tool_call: dict[str, Any]) -> str:
    function = tool_call.get("function", {})
    if not isinstance(function, dict):
        return json.dumps(tool_call, ensure_ascii=False, separators=(",", ":"))

    name = str(function.get("name", "") or "tool")
    arguments = _parse_tool_arguments(function.get("arguments"))
    for key in ("command", "cmd", "file_path", "filepath", "path"):
        value = arguments.get(key)
        if value:
            return f"{name} {value}".strip()
    if arguments:
        return f"{name} {json.dumps(arguments, ensure_ascii=False, separators=(',', ':'))}"
    return name


def _kimi_messages_to_host_events(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    command_by_tool_id: dict[str, str] = {}
    for message in messages:
        role = str(message.get("role", ""))
        if role == "assistant":
            content = content_to_text(message.get("content"))
            if content:
                events.append(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": content,
                        },
                    }
                )

            for tool_call in message.get("tool_calls", []) or []:
                if not isinstance(tool_call, dict):
                    continue
                tool_id = str(tool_call.get("id", "") or "")
                command = _tool_call_command(tool_call)
                if tool_id:
                    command_by_tool_id[tool_id] = command
                events.append(
                    {
                        "type": "item.started",
                        "item": {
                            "type": "command_execution",
                            "command": command,
                        },
                    }
                )
            continue

        if role == "tool":
            tool_id = str(message.get("tool_call_id", "") or "")
            events.append(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": command_by_tool_id.get(tool_id, ""),
                        "aggregated_output": content_to_text(message.get("content")),
                        "status": "completed",
                    },
                }
            )

    return events


def _extract_assistant_messages(messages: list[dict[str, Any]]) -> list[str]:
    extracted: list[str] = []
    for message in messages:
        if str(message.get("role", "")) != "assistant":
            continue
        text = content_to_text(message.get("content"))
        if text:
            extracted.append(text)
    return extracted


def _build_kimi_args(
    *,
    session_dir: Path,
    skills_dir: Path,
    package_dir: Path,
    session_id: str | None,
    text: str,
    model: str | None,
) -> list[str]:
    return build_kimi_args(
        work_dir=session_dir,
        prompt=text,
        output_format="stream-json",
        add_dir=package_dir,
        skills_dir=skills_dir,
        session_id=session_id,
        model=model,
    )


class KimiCodeHost:
    def __init__(
        self,
        *,
        session_root: str | Path,
        command_runner: CommandRunner | None = None,
        timeout_seconds: int | None = 180,
        model: str | None = None,
    ) -> None:
        self.session_root = Path(session_root)
        self.command_runner = command_runner or default_kimi_command_runner
        self.timeout_seconds = timeout_seconds
        self.model = model

    def prepare_session(self, package_dir: str | Path, eval_case: dict[str, Any]) -> dict[str, Any]:
        package_path = Path(package_dir).resolve()
        package_skill_path = package_path / "SKILL.md"
        metadata = extract_frontmatter(read_text(package_skill_path))

        session_dir = self.session_root
        skills_dir = session_dir / ".kimi" / "skills"
        proxy_skill_dir = skills_dir / package_path.name
        proxy_skill_dir.mkdir(parents=True, exist_ok=True)
        proxy_skill_path = proxy_skill_dir / "SKILL.md"
        proxy_skill_path.write_text(
            render_proxy_skill(package_path, package_skill_path, metadata),
            encoding="utf-8",
        )

        eval_id = int(eval_case.get("id", eval_case.get("eval_id", 0)) or 0)
        session_seed = f"vision-skill-{package_path.name}-{eval_id}-{uuid.uuid4().hex[:10]}"
        return {
            "host_backend": "kimi-code",
            "package_name": package_path.name,
            "package_dir": str(package_path),
            "canonical_skill_path": str(package_skill_path),
            "proxy_skill_path": str(proxy_skill_path),
            "skills_dir": str(skills_dir),
            "session_dir": str(session_dir),
            "eval_id": eval_id,
            "thread_id": None,
            "kimi_session_id": None,
            "session_seed": session_seed,
            "turns": [],
            "stderr": [],
        }

    def send_user_turn(self, session_handle: dict[str, Any], text: str) -> dict[str, Any]:
        session_dir = Path(session_handle["session_dir"])
        os.environ.setdefault("PYTHONUTF8", "1")
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        args = _build_kimi_args(
            session_dir=session_dir,
            skills_dir=Path(session_handle["skills_dir"]),
            package_dir=Path(session_handle["package_dir"]),
            session_id=session_handle.get("kimi_session_id"),
            text=text,
            model=self.model,
        )

        result = self.command_runner(args, session_dir, self.timeout_seconds)
        if int(result.get("returncode", 0) or 0) != 0:
            raise RuntimeError(
                "Kimi Code host execution failed: "
                + str(result.get("stderr", "") or result.get("stdout", "")).strip()
            )

        parsed_messages, warnings = parse_jsonl(str(result.get("stdout", "")))
        messages = [message for message in parsed_messages if isinstance(message, dict)]
        if not messages and str(result.get("stdout", "")).strip():
            messages = [{"role": "assistant", "content": str(result.get("stdout", "")).strip()}]
        stderr_lines = str(result.get("stderr", "")).splitlines()
        resolved_session_id = extract_resume_session_id(warnings + stderr_lines)
        if resolved_session_id:
            session_handle["kimi_session_id"] = resolved_session_id
            session_handle["thread_id"] = resolved_session_id

        assistant_messages = _extract_assistant_messages(messages)
        assistant_text = assistant_messages[-1] if assistant_messages else ""
        events = _kimi_messages_to_host_events(messages)
        command_events = [
            event["item"]
            for event in events
            if event.get("type") == "item.completed"
            and event.get("item", {}).get("type") == "command_execution"
        ]

        turn = {
            "turn_index": len(session_handle["turns"]) + 1,
            "user_text": text,
            "assistant_text": assistant_text,
            "events": events,
            "command_events": command_events,
            "warnings": warnings,
            "stderr": str(result.get("stderr", "")),
        }
        session_handle["turns"].append(turn)
        if result.get("stderr"):
            session_handle.setdefault("stderr", []).append(str(result["stderr"]))

        return {
            "thread_id": session_handle["thread_id"],
            "assistant_text": assistant_text,
            "events": events,
            "warnings": warnings,
            "command_events": command_events,
        }

    def read_transcript(self, session_handle: dict[str, Any]) -> dict[str, Any]:
        return {
            "thread_id": session_handle.get("thread_id"),
            "host_backend": "kimi-code",
            "package_name": session_handle.get("package_name", ""),
            "package_dir": session_handle.get("package_dir", ""),
            "proxy_skill_path": session_handle.get("proxy_skill_path", ""),
            "canonical_skill_path": session_handle.get("canonical_skill_path", ""),
            "skills_dir": session_handle.get("skills_dir", ""),
            "turns": list(session_handle.get("turns", [])),
            "stderr": list(session_handle.get("stderr", [])),
        }

    def detect_skill_trigger(self, transcript: dict[str, Any], package_name: str) -> dict[str, Any]:
        normalized_events = normalize_host_transcript(transcript)
        signal_report = extract_host_signals(transcript, normalized_events)
        signal_type_map = {
            "skill_proxy_read": "proxy_skill_read",
            "skill_canonical_read": "canonical_skill_read",
            "skill_meta_read": "skill_meta_read",
        }
        evidence: list[dict[str, Any]] = []
        for snippet in signal_report.get("evidence_snippets", []):
            if snippet.get("label") not in {"skill_proxy_read", "skill_canonical_read", "skill_meta_read"}:
                continue
            evidence.append(
                {
                    "type": signal_type_map.get(str(snippet.get("label", "")), str(snippet.get("label", ""))),
                    "turn_index": snippet.get("turn_index"),
                    "raw_ref": snippet.get("raw_ref", ""),
                    "detail": snippet.get("text", ""),
                }
            )

        triggered = bool(
            signal_report["trigger_signals"]["proxy_skill_read"]
            or signal_report["trigger_signals"]["canonical_skill_read"]
            or signal_report["trigger_signals"]["skill_meta_read"]
        )
        return {
            "package_name": package_name,
            "triggered": triggered,
            "false_trigger": False,
            "expected_trigger": None,
            "expected_trigger_signals": [],
            "trigger_turn_index": signal_report["trigger_signals"]["trigger_turn_index"],
            "first_answer_turn_index": signal_report["trigger_signals"]["first_answer_turn_index"],
            "first_skill_read_turn_index": signal_report["trigger_signals"]["first_skill_read_turn_index"],
            "skill_read_before_first_answer": signal_report["trigger_signals"]["skill_read_before_first_answer"],
            "observed_trigger_signals": {
                "proxy_skill_read": signal_report["trigger_signals"]["proxy_skill_read"],
                "canonical_skill_read": signal_report["trigger_signals"]["canonical_skill_read"],
                "skill_meta_read": signal_report["trigger_signals"]["skill_meta_read"],
                "explicit_skill_use_announcement": signal_report["trigger_signals"]["explicit_skill_use_announcement"],
            },
            "evidence": evidence,
        }

    def close_session(self, session_handle: dict[str, Any]) -> dict[str, Any]:
        return {
            "closed": True,
            "thread_id": session_handle.get("thread_id"),
            "session_dir": session_handle.get("session_dir", ""),
        }


__all__ = ["KimiCodeHost"]
