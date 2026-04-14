from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import re
from typing import Any, Callable

from toolchain.agent_hosts.event_normalizer import normalize_host_transcript
from toolchain.agent_hosts.signal_extractor import extract_host_signals


CommandRunner = Callable[[list[str], Path, int | None], dict[str, Any]]

CHECKPOINT_MARKERS = [
    "继续",
    "不对",
    "直接要结果",
    "暂停确认",
    "pause for confirmation",
]
MISSING_INFO_KEYWORDS = [
    "还缺",
    "补充",
    "missing information",
    "before i can",
    "need more context",
]
REVISE_KEYWORDS = ["不对", "修改", "revise"]
CONTINUE_KEYWORDS = ["继续", "continue"]
DIRECT_RESULT_KEYWORDS = ["直接要结果", "直接给我", "不用确认", "skip checkpoint"]
SWOT_GROUPS = [
    ["strengths", "优势"],
    ["weaknesses", "劣势"],
    ["opportunities", "机会"],
    ["threats", "威胁"],
]


def _default_command_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, Any]:
    run_args = args
    if os.name == "nt":
        def _quote(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        run_args = [
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "-NoProfile",
            "-Command",
            "& " + " ".join(_quote(item) for item in args),
        ]
    completed = subprocess.run(
        run_args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds or None,
    )
    return {
        "returncode": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_frontmatter(skill_text: str) -> dict[str, str]:
    if not skill_text.startswith("---"):
        return {"name": "", "description": ""}
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", skill_text, re.DOTALL)
    if not match:
        return {"name": "", "description": ""}
    values: dict[str, str] = {"name": "", "description": ""}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key in values:
            values[key] = raw_value.strip()
    return values


def _render_proxy_skill(package_dir: Path, package_skill_path: Path, metadata: dict[str, str]) -> str:
    name = metadata.get("name") or package_dir.name
    description = metadata.get("description") or f"Use this skill whenever the user needs help with {package_dir.name}."
    return "\n".join(
        [
            "---",
            f"name: {name}",
            f"description: {description}",
            "---",
            "",
            "# Host Proxy",
            "",
            "This is a workspace-local proxy used for host evaluation.",
            f"Canonical package directory: {package_dir}",
            f"Canonical skill file: {package_skill_path}",
            "",
            "When this skill triggers:",
            f"1. Read the canonical skill file at `{package_skill_path}`.",
            f"2. Follow the canonical package instructions and resources from `{package_dir}`.",
            "3. Do not announce that you are using a proxy skill.",
            "4. Preserve the original protocol behavior from the canonical skill.",
            "",
        ]
    ).strip() + "\n"


def _parse_jsonl(output_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    warnings: list[str] = []
    for raw_line in output_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            warnings.append(raw_line)
    return events, warnings


def _extract_thread_id(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("type") == "thread.started":
            return str(event.get("thread_id", ""))
    return None


def _extract_command_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for event in events:
        item = event.get("item", {})
        if item.get("type") == "command_execution":
            extracted.append(
                {
                    "command": str(item.get("command", "")),
                    "aggregated_output": str(item.get("aggregated_output", "")),
                    "status": str(item.get("status", "")),
                }
            )
    return extracted


def _extract_agent_messages(events: list[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    for event in events:
        item = event.get("item", {})
        if item.get("type") == "agent_message":
            messages.append(str(item.get("text", "")).strip())
    return [message for message in messages if message]


class CodexHost:
    def __init__(
        self,
        *,
        session_root: str | Path,
        command_runner: CommandRunner | None = None,
        timeout_seconds: int | None = 180,
    ) -> None:
        self.session_root = Path(session_root)
        self.command_runner = command_runner or _default_command_runner
        self.timeout_seconds = timeout_seconds

    def prepare_session(self, package_dir: str | Path, eval_case: dict[str, Any]) -> dict[str, Any]:
        package_path = Path(package_dir)
        package_skill_path = package_path / "SKILL.md"
        metadata = _extract_frontmatter(_read_text(package_skill_path))

        session_dir = self.session_root
        proxy_skill_dir = session_dir / ".codex" / "skills" / package_path.name
        proxy_skill_dir.mkdir(parents=True, exist_ok=True)
        proxy_skill_path = proxy_skill_dir / "SKILL.md"
        proxy_skill_path.write_text(
            _render_proxy_skill(package_path, package_skill_path, metadata),
            encoding="utf-8",
        )

        return {
            "package_name": package_path.name,
            "package_dir": str(package_path),
            "canonical_skill_path": str(package_skill_path),
            "proxy_skill_path": str(proxy_skill_path),
            "session_dir": str(session_dir),
            "eval_id": int(eval_case.get("id", eval_case.get("eval_id", 0)) or 0),
            "thread_id": None,
            "turns": [],
            "stderr": [],
        }

    def send_user_turn(self, session_handle: dict[str, Any], text: str) -> dict[str, Any]:
        session_dir = Path(session_handle["session_dir"])
        thread_id = session_handle.get("thread_id")
        if thread_id:
            args = [
                "codex",
                "exec",
                "--skip-git-repo-check",
                "-C",
                str(session_dir),
                "resume",
                "--json",
                str(thread_id),
                text,
            ]
        else:
            args = [
                "codex",
                "exec",
                "--json",
                "--skip-git-repo-check",
                "-C",
                str(session_dir),
                text,
            ]

        result = self.command_runner(args, session_dir, self.timeout_seconds)
        if int(result.get("returncode", 0) or 0) != 0:
            raise RuntimeError(
                "Codex host execution failed: "
                + str(result.get("stderr", "") or result.get("stdout", "")).strip()
            )

        events, warnings = _parse_jsonl(str(result.get("stdout", "")))
        resolved_thread_id = _extract_thread_id(events) or thread_id
        assistant_messages = _extract_agent_messages(events)
        assistant_text = assistant_messages[-1] if assistant_messages else ""
        command_events = _extract_command_events(events)

        turn = {
            "turn_index": len(session_handle["turns"]) + 1,
            "user_text": text,
            "assistant_text": assistant_text,
            "events": events,
            "command_events": command_events,
            "warnings": warnings,
            "stderr": str(result.get("stderr", "")),
        }
        session_handle["thread_id"] = resolved_thread_id
        session_handle["turns"].append(turn)
        if result.get("stderr"):
            session_handle.setdefault("stderr", []).append(str(result["stderr"]))

        return {
            "thread_id": resolved_thread_id,
            "assistant_text": assistant_text,
            "events": events,
            "warnings": warnings,
            "command_events": command_events,
        }

    def read_transcript(self, session_handle: dict[str, Any]) -> dict[str, Any]:
        return {
            "thread_id": session_handle.get("thread_id"),
            "package_name": session_handle.get("package_name", ""),
            "package_dir": session_handle.get("package_dir", ""),
            "proxy_skill_path": session_handle.get("proxy_skill_path", ""),
            "canonical_skill_path": session_handle.get("canonical_skill_path", ""),
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
