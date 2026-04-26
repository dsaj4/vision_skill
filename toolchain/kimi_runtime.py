from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable


DEFAULT_KIMI_TIMEOUT_SECONDS = 240
CommandRunner = Callable[[list[str], Path, int | None], dict[str, Any]]


def resolve_kimi_command() -> str:
    explicit = (os.getenv("KIMI_CLI_EXECUTABLE") or "").strip()
    if explicit and Path(explicit).exists():
        return explicit

    for candidate in ("kimi", "kimi.exe"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    home = Path.home()
    fallback_paths = [
        home / ".local" / "bin" / "kimi.exe",
        home / ".local" / "bin" / "kimi-cli.exe",
        home / "AppData" / "Roaming" / "npm" / "kimi.cmd",
        home / "AppData" / "Roaming" / "npm" / "kimi.exe",
    ]
    for path in fallback_paths:
        if path.exists():
            return str(path)

    return "kimi"


def ensure_kimi_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PATH", "")
    user_bin = str(Path.home() / ".local" / "bin")
    if user_bin not in env["PATH"].split(";"):
        env["PATH"] = user_bin + ";" + env["PATH"]
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def resolve_kimi_model(model: str | None = None) -> str | None:
    return (model or os.getenv("KIMI_CLI_MODEL") or "").strip() or None


def resolve_kimi_timeout(timeout_seconds: int | None, default: int = DEFAULT_KIMI_TIMEOUT_SECONDS) -> int:
    if timeout_seconds is not None:
        return int(timeout_seconds)
    return default


def build_kimi_args(
    *,
    work_dir: str | Path,
    prompt: str,
    model: str | None = None,
    output_format: str | None = None,
    final_message_only: bool = False,
    add_dir: str | Path | None = None,
    skills_dir: str | Path | None = None,
    session_id: str | None = None,
) -> list[str]:
    args = [
        resolve_kimi_command(),
        "--print",
    ]
    if output_format:
        args.append(f"--output-format={output_format}")
    if final_message_only:
        args.append("--final-message-only")
    args.extend(["--work-dir", str(work_dir)])
    if add_dir is not None:
        args.extend(["--add-dir", str(add_dir)])
    if skills_dir is not None:
        args.extend(["--skills-dir", str(skills_dir)])
    if session_id:
        args.extend(["--session", session_id])
    resolved_model = resolve_kimi_model(model)
    if resolved_model:
        args.extend(["--model", resolved_model])
    args.extend(["--prompt", prompt])
    return args


def default_kimi_command_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
        env=ensure_kimi_env(),
    )
    return {
        "returncode": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_jsonl(output_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    messages: list[dict[str, Any]] = []
    warnings: list[str] = []
    for raw_line in output_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(raw_line)
            continue
        if isinstance(parsed, dict):
            messages.append(parsed)
        else:
            warnings.append(raw_line)
    return messages, warnings


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
        return "\n".join(part for part in parts if part).strip()
    if content is None:
        return ""
    return str(content).strip()


def extract_assistant_message(messages: list[dict[str, Any]], fallback_stdout: str = "") -> str:
    extracted: list[str] = []
    for message in messages:
        if str(message.get("role", "")) != "assistant":
            continue
        text = content_to_text(message.get("content"))
        if text:
            extracted.append(text)
    if extracted:
        return extracted[-1]
    return fallback_stdout.strip()


def extract_resume_session_id(text_or_lines: str | list[str]) -> str | None:
    lines = text_or_lines.splitlines() if isinstance(text_or_lines, str) else text_or_lines
    for line in reversed(lines):
        match = re.search(r"kimi\s+-r\s+([A-Za-z0-9_.:-]+)", line)
        if match:
            return match.group(1)
    return None


def messages_to_prompt(messages: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for message in messages:
        role = str(message.get("role", "user")).strip().lower() or "user"
        content = content_to_text(message.get("content"))
        if not content:
            continue
        blocks.extend([f"[{role}]", content, ""])
    return "\n".join(blocks).strip()


def run_kimi_prompt(
    prompt: str,
    *,
    work_dir: str | Path,
    model: str | None = None,
    timeout_seconds: int | None = None,
    command_runner: CommandRunner | None = None,
    final_message_only: bool = True,
) -> dict[str, Any]:
    """Run a direct Kimi prompt and return terminal text.

    Compatibility helper only. The evaluation mainline should prefer
    `toolchain.kimi_workspace.run_kimi_workspace_task` so outputs are produced
    as controlled workspace files.
    """
    resolved_work_dir = Path(work_dir)
    resolved_work_dir.mkdir(parents=True, exist_ok=True)
    args = build_kimi_args(
        work_dir=resolved_work_dir,
        prompt=prompt,
        model=model,
        final_message_only=final_message_only,
    )
    runner = command_runner or default_kimi_command_runner
    result = runner(args, resolved_work_dir, timeout_seconds)
    if int(result.get("returncode", 0) or 0) != 0:
        raise RuntimeError(
            "Kimi CLI prompt execution failed: "
            + str(result.get("stderr", "") or result.get("stdout", "")).strip()
        )
    stdout = str(result.get("stdout", ""))
    messages, warnings = parse_jsonl(stdout)
    assistant_text = extract_assistant_message(messages, fallback_stdout=stdout)
    return {
        "assistant_text": assistant_text,
        "raw_result": result,
        "messages": messages,
        "warnings": warnings,
    }


def run_kimi_messages(
    messages: list[dict[str, Any]],
    *,
    work_dir: str | Path,
    model: str | None = None,
    timeout_seconds: int | None = None,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Compatibility Chat-Completions-shaped wrapper around `run_kimi_prompt`."""
    prompt = messages_to_prompt(messages)
    result = run_kimi_prompt(
        prompt,
        work_dir=work_dir,
        model=model,
        timeout_seconds=timeout_seconds,
        command_runner=command_runner,
        final_message_only=True,
    )
    return {
        "choices": [{"message": {"role": "assistant", "content": result["assistant_text"]}}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "kimi": {
            "messages": result["messages"],
            "warnings": result["warnings"],
            "stderr": str(result["raw_result"].get("stderr", "")),
        },
    }
