from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.common import load_json, read_text, write_json, write_text
from toolchain.kimi_runtime import (
    CommandRunner,
    build_kimi_args,
    default_kimi_command_runner,
    extract_assistant_message,
    parse_jsonl,
    resolve_kimi_model,
    resolve_kimi_timeout,
)


DEFAULT_TIMEOUT_SECONDS = 240


def _safe_relative_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError(f"Workspace task paths must be relative and stay inside the task dir: {relative_path}")
    return path


def write_workspace_task(
    task_dir: str | Path,
    *,
    task_markdown: str,
    required_outputs: list[str],
    inputs: dict[str, Any] | None = None,
    contract_markdown: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a bounded Kimi workspace task bundle.

    Kimi is expected to read these files and write required outputs. The CLI
    terminal response is treated as log metadata only.
    """

    root = Path(task_dir)
    root.mkdir(parents=True, exist_ok=True)
    normalized_required_outputs = [_safe_relative_path(path).as_posix() for path in required_outputs]
    write_text(root / "task.md", task_markdown.strip() + "\n")
    if contract_markdown:
        write_text(root / "contracts" / "output-contract.md", contract_markdown.strip() + "\n")

    written_inputs: list[str] = []
    for relative_path, value in (inputs or {}).items():
        target = root / _safe_relative_path(relative_path)
        if isinstance(value, str):
            write_text(target, value)
        else:
            write_json(target, value)
        written_inputs.append(relative_path)

    manifest = {
        "metadata": {
            **(metadata or {}),
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "task_file": "task.md",
        "contract_file": "contracts/output-contract.md" if contract_markdown else "",
        "input_files": sorted(written_inputs),
        "required_outputs": normalized_required_outputs,
        "result_source_of_truth": "workspace-output-files",
        "terminal_response_policy": "log-only",
    }
    write_json(root / "workspace-manifest.json", manifest)
    return manifest


def run_kimi_workspace_task(
    task_dir: str | Path,
    *,
    required_outputs: list[str],
    model: str | None = None,
    timeout_seconds: int | None = None,
    command_runner: CommandRunner | None = None,
    add_dir: str | Path | None = None,
    skills_dir: str | Path | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    run_dir = Path(task_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    resolved_model = resolve_kimi_model(model)
    task_prompt = (
        prompt
        or "Read task.md and workspace-manifest.json in this workspace. "
        "Write the required output files exactly as specified. "
        "Keep the terminal reply to one short status line."
    )
    args = build_kimi_args(
        work_dir=run_dir,
        prompt=task_prompt,
        model=resolved_model,
        output_format="stream-json",
        add_dir=add_dir,
        skills_dir=skills_dir,
    )

    result = (command_runner or default_kimi_command_runner)(
        args,
        run_dir,
        resolve_kimi_timeout(timeout_seconds, DEFAULT_TIMEOUT_SECONDS),
    )
    if int(result.get("returncode", 0) or 0) != 0:
        raise RuntimeError(
            "Kimi workspace task failed: "
            + str(result.get("stderr", "") or result.get("stdout", "")).strip()
        )

    stdout = str(result.get("stdout", ""))
    messages, warnings = parse_jsonl(stdout)
    assistant_text = extract_assistant_message(messages, fallback_stdout=stdout)

    resolved_outputs: dict[str, str] = {}
    missing_outputs: list[str] = []
    for relative_path in required_outputs:
        target = run_dir / _safe_relative_path(relative_path)
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
        "raw_result": result,
    }


def read_workspace_text(task_result: dict[str, Any], relative_path: str) -> str:
    resolved = task_result.get("resolved_outputs", {}).get(relative_path)
    if not resolved:
        raise KeyError(f"Workspace output was not resolved: {relative_path}")
    return read_text(resolved)


def load_workspace_json(task_result: dict[str, Any], relative_path: str) -> Any:
    resolved = task_result.get("resolved_outputs", {}).get(relative_path)
    if not resolved:
        raise KeyError(f"Workspace output was not resolved: {relative_path}")
    return load_json(resolved)
