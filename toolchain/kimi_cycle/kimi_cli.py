from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from toolchain.kimi_command import resolve_kimi_command


DEFAULT_TIMEOUT_SECONDS = 240
CommandRunner = Callable[[list[str], Path, int | None], dict[str, Any]]


def _resolve_model(model: str | None) -> str | None:
    return (model or os.getenv("KIMI_CLI_MODEL") or "").strip() or None


def _resolve_timeout(timeout_seconds: int | None) -> int:
    if timeout_seconds is not None:
        return int(timeout_seconds)
    return DEFAULT_TIMEOUT_SECONDS


def _ensure_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PATH", "")
    user_bin = str(Path.home() / ".local" / "bin")
    if user_bin not in env["PATH"].split(";"):
        env["PATH"] = user_bin + ";" + env["PATH"]
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _default_command_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
        env=_ensure_env(),
    )
    return {
        "returncode": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _extract_assistant_text(stdout: str) -> str:
    return stdout.strip()


def _parse_jsonl(output_text: str) -> tuple[list[dict[str, Any]], list[str]]:
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


def _content_to_text(content: Any) -> str:
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


def _extract_assistant_message(messages: list[dict[str, Any]], stdout: str) -> str:
    extracted: list[str] = []
    for message in messages:
        if str(message.get("role", "")) != "assistant":
            continue
        text = _content_to_text(message.get("content"))
        if text:
            extracted.append(text)
    if extracted:
        return extracted[-1]
    return stdout.strip()


def compact_text(text: str, max_chars: int) -> str:
    normalized = text.strip()
    if len(normalized) <= max_chars:
        return normalized
    head = normalized[: max_chars // 2].strip()
    tail = normalized[-max(300, max_chars // 3) :].strip()
    return f"{head}\n\n...[truncated]...\n\n{tail}"


def extract_json_object(text: str) -> dict[str, Any]:
    payload = text.strip()
    fenced = re.search(r"```json\s*(\{.*\})\s*```", payload, re.DOTALL)
    candidate = fenced.group(1) if fenced else payload
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Kimi output did not contain a JSON object.")
    return json.loads(candidate[start : end + 1])


def extract_markdown_document(text: str) -> str:
    payload = text.strip()
    fenced = re.fullmatch(r"```(?:markdown|md)?\s*(.*?)\s*```", payload, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else payload
    return candidate.strip()


def run_kimi_prompt(
    prompt: str,
    work_dir: str | Path,
    *,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    run_dir = Path(work_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved_model = _resolve_model(model)
    args = [
        resolve_kimi_command(),
        "--print",
        "--final-message-only",
        "--work-dir",
        str(run_dir),
    ]
    if resolved_model:
        args.extend(["--model", resolved_model])
    args.extend(["--prompt", prompt])

    completed = subprocess.run(
        args,
        cwd=str(run_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=_resolve_timeout(timeout_seconds),
        env=_ensure_env(),
    )
    if int(completed.returncode) != 0:
        raise RuntimeError(
            "Kimi CLI prompt execution failed: "
            + (completed.stderr or completed.stdout).strip()
        )

    assistant_text = _extract_assistant_text(completed.stdout)
    return {
        "command": args,
        "assistant_text": assistant_text,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "work_dir": str(run_dir),
        "model": resolved_model or "",
    }


def run_kimi_workspace_task(
    prompt: str,
    task_dir: str | Path,
    *,
    required_outputs: list[str],
    model: str | None = None,
    timeout_seconds: int | None = None,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    run_dir = Path(task_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved_model = _resolve_model(model)
    args = [
        resolve_kimi_command(),
        "--print",
        "--output-format=stream-json",
        "--work-dir",
        str(run_dir),
    ]
    if resolved_model:
        args.extend(["--model", resolved_model])
    args.extend(["--prompt", prompt])

    result = (command_runner or _default_command_runner)(
        args,
        run_dir,
        _resolve_timeout(timeout_seconds),
    )
    if int(result.get("returncode", 0) or 0) != 0:
        raise RuntimeError(
            "Kimi workspace task failed: "
            + str(result.get("stderr", "") or result.get("stdout", "")).strip()
        )

    stdout = str(result.get("stdout", ""))
    messages, warnings = _parse_jsonl(stdout)
    assistant_text = _extract_assistant_message(messages, stdout)
    resolved_outputs: dict[str, str] = {}
    missing_outputs: list[str] = []
    for relative_path in required_outputs:
        target = run_dir / relative_path
        if target.exists():
            resolved_outputs[relative_path] = str(target)
        else:
            missing_outputs.append(relative_path)
    if missing_outputs:
        raise RuntimeError(
            "Kimi workspace task did not produce required outputs: "
            + ", ".join(missing_outputs)
        )

    return {
        "command": args,
        "assistant_text": assistant_text,
        "stdout": stdout,
        "stderr": str(result.get("stderr", "")),
        "warnings": warnings,
        "messages": messages,
        "work_dir": str(run_dir),
        "model": resolved_model or "",
        "resolved_outputs": resolved_outputs,
    }
