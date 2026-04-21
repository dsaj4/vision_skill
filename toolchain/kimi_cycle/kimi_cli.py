from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 240


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


def _extract_assistant_text(stdout: str) -> str:
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
    fenced = re.search(r"```(?:markdown|md)?\s*(.*?)```", payload, re.DOTALL | re.IGNORECASE)
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
        "kimi",
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
