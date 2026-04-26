from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from toolchain.common import compact_text, extract_json_object
from toolchain.kimi_runtime import (
    CommandRunner,
    build_kimi_args,
    default_kimi_command_runner,
    resolve_kimi_model,
    resolve_kimi_timeout,
)
from toolchain.kimi_workspace import run_kimi_workspace_task as run_shared_kimi_workspace_task


DEFAULT_TIMEOUT_SECONDS = 240


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
    resolved_model = resolve_kimi_model(model)
    args = build_kimi_args(
        work_dir=run_dir,
        prompt=prompt,
        model=resolved_model,
        final_message_only=True,
    )
    completed = default_kimi_command_runner(
        args,
        run_dir,
        resolve_kimi_timeout(timeout_seconds, DEFAULT_TIMEOUT_SECONDS),
    )
    if int(completed.get("returncode", 0) or 0) != 0:
        raise RuntimeError(
            "Kimi CLI prompt execution failed: "
            + str(completed.get("stderr", "") or completed.get("stdout", "")).strip()
        )

    stdout = str(completed.get("stdout", ""))
    assistant_text = stdout.strip()
    return {
        "command": args,
        "assistant_text": assistant_text,
        "stdout": stdout,
        "stderr": str(completed.get("stderr", "")),
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
    return run_shared_kimi_workspace_task(
        task_dir,
        required_outputs=required_outputs,
        model=model,
        timeout_seconds=timeout_seconds,
        command_runner=command_runner,
        prompt=prompt,
    )
