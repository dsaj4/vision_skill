from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolchain.agent_hosts.host_utils import extract_frontmatter, render_proxy_skill
from toolchain.common import load_json, write_json, write_text
from toolchain.kimi_runtime import CommandRunner
from toolchain.kimi_workspace import load_workspace_json, read_workspace_text, run_kimi_workspace_task, write_workspace_task


DEFAULT_TIMEOUT_SECONDS = 300


def _run_is_complete(run_dir: Path) -> bool:
    required_paths = [
        run_dir / "raw_response.json",
        run_dir / "transcript.json",
        run_dir / "timing.json",
        run_dir / "outputs" / "final_response.md",
        run_dir / "outputs" / "latest_assistant_response.md",
    ]
    return all(path.exists() for path in required_paths)


def _resolve_eval_file(file_ref: str, package_dir: Path, iteration_dir: Path) -> Path | None:
    candidate = Path(file_ref)
    candidates = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        candidates.extend(
            [
                package_dir / file_ref,
                iteration_dir / file_ref,
                Path.cwd() / file_ref,
            ]
        )
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _render_file_context(file_refs: list[str], package_dir: Path, iteration_dir: Path) -> tuple[str, list[dict[str, str]]]:
    if not file_refs:
        return "", []

    loaded_files: list[dict[str, str]] = []
    blocks: list[str] = []
    for file_ref in file_refs:
        resolved = _resolve_eval_file(file_ref, package_dir, iteration_dir)
        if resolved is None:
            loaded_files.append({"file": file_ref, "status": "missing"})
            continue
        content = resolved.read_text(encoding="utf-8")
        loaded_files.append({"file": file_ref, "resolved_path": str(resolved), "status": "loaded"})
        blocks.extend(
            [
                "",
                f"[File: {resolved.name}]",
                content,
                f"[End File: {resolved.name}]",
            ]
        )

    if not blocks:
        return "", loaded_files

    return "\n".join(["Use the following input files as additional context:"] + blocks), loaded_files


def _normalize_turn_script_items(script: Any) -> list[dict[str, str]]:
    if not script:
        return []
    turns: list[dict[str, str]] = []
    for item in script:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            label = str(item.get("label", "")).strip()
        else:
            text = str(item).strip()
            label = ""
        if text:
            turns.append({"text": text, "label": label})
    return turns


def _turn_script(eval_metadata: dict[str, Any], user_prompt: str) -> dict[str, Any]:
    execution_eval = eval_metadata.get("execution_eval", {})
    if isinstance(execution_eval, dict):
        execution_turns = _normalize_turn_script_items(execution_eval.get("turn_script", []))
        if execution_turns:
            return {
                "source": "execution_eval.turn_script",
                "execution_eval": execution_eval,
                "turns": execution_turns,
            }

    host_eval = eval_metadata.get("host_eval", {})
    if isinstance(host_eval, dict):
        host_turns = _normalize_turn_script_items(host_eval.get("turn_script", []))
        if host_turns:
            return {
                "source": "host_eval.turn_script",
                "execution_eval": execution_eval if isinstance(execution_eval, dict) else {},
                "turns": host_turns,
            }

    return {
        "source": "prompt",
        "execution_eval": execution_eval if isinstance(execution_eval, dict) else {},
        "turns": [{"text": user_prompt, "label": "prompt"}],
    }


def _latest_assistant_response_from_transcript(transcript: dict[str, Any]) -> str:
    turns = transcript.get("turns", [])
    if not turns:
        return ""
    return str(turns[-1].get("assistant_text", "")).strip()


def _full_conversation_from_transcript(transcript: dict[str, Any]) -> str:
    lines = ["# Full Conversation", ""]
    for turn in transcript.get("turns", []):
        turn_index = int(turn.get("turn_index", 0) or 0)
        label = str(turn.get("label", "")).strip()
        label_suffix = f" ({label})" if label else ""
        lines.extend(
            [
                f"## Turn {turn_index} User{label_suffix}",
                "",
                str(turn.get("user_text", "")).strip(),
                "",
                f"## Turn {turn_index} Assistant",
                "",
                str(turn.get("assistant_text", "")).strip(),
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _write_turn_outputs(run_dir: Path, transcript: dict[str, Any]) -> None:
    turns_dir = run_dir / "outputs" / "turns"
    for turn in transcript.get("turns", []):
        turn_index = int(turn.get("turn_index", 0) or 0)
        if turn_index <= 0:
            continue
        write_text(
            turns_dir / f"turn-{turn_index}-assistant.md",
            str(turn.get("assistant_text", "")).strip() + "\n",
        )


def _execution_model(model: str | None) -> str:
    return (model or "").strip() or "kimi-cli-default"


def _session_root(iteration_dir: Path, eval_metadata: dict[str, Any], configuration: str, run_dir: Path) -> Path:
    eval_id = int(eval_metadata.get("eval_id", 0) or 0)
    return iteration_dir / ".kimi-sessions" / f"e{eval_id}-{configuration}-{run_dir.name}"


def execute_run(
    run_path: str | Path,
    package_path: str | Path,
    configuration: str | None = None,
    *,
    command_runner: CommandRunner | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_path)
    package_dir = Path(package_path)
    eval_dir = run_dir.parent.parent
    iteration_dir = eval_dir.parent
    resolved_configuration = configuration or run_dir.parent.name
    resolved_timeout = int(timeout_seconds or DEFAULT_TIMEOUT_SECONDS)
    resolved_model = _execution_model(model)

    eval_metadata = load_json(eval_dir / "eval_metadata.json")
    file_context, loaded_files = _render_file_context(
        [str(item) for item in eval_metadata.get("files", [])],
        package_dir,
        iteration_dir,
    )
    user_prompt = str(eval_metadata.get("prompt", ""))
    if file_context:
        user_prompt = f"{user_prompt}\n\n{file_context}"
    script = _turn_script(eval_metadata, user_prompt)
    turns = script["turns"]

    request_payload = {
        "runner": "kimi-code",
        "configuration": resolved_configuration,
        "model": resolved_model,
        "turns": turns,
        "turn_script_source": script["source"],
        "execution_eval": script["execution_eval"],
        "host_eval": eval_metadata.get("host_eval", {}),
        "loaded_files": loaded_files,
        "execution_mode": "workspace-file-task",
        "final_response_mode": "full_conversation",
        "result_source_of_truth": "outputs/final_response.md",
        "latest_assistant_response_path": "outputs/latest_assistant_response.md",
        "skill_mode": "workspace-file-task-proxy" if resolved_configuration == "with_skill" else "workspace-file-task-baseline",
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "request.json", request_payload)

    started_at = datetime.now(timezone.utc)
    start = time.perf_counter()
    session_root = _session_root(iteration_dir, eval_metadata, resolved_configuration, run_dir)
    transcript = _run_workspace_file_turns(
        turns,
        session_dir=session_root,
        package_dir=package_dir,
        configuration=resolved_configuration,
        timeout_seconds=resolved_timeout,
        model=model,
        command_runner=command_runner,
    )
    raw_response = {
        "runner": "kimi-code",
        "mode": resolved_configuration,
        "execution_mode": "workspace-file-task",
        "result_source_of_truth": str(run_dir / "outputs" / "final_response.md"),
        "transcript": transcript,
    }

    duration_seconds = time.perf_counter() - start
    finished_at = datetime.now(timezone.utc)
    latest_assistant_text = _latest_assistant_response_from_transcript(transcript)
    full_conversation = _full_conversation_from_transcript(transcript)

    write_json(run_dir / "raw_response.json", raw_response)
    write_text(run_dir / "outputs" / "final_response.md", full_conversation)
    write_text(run_dir / "outputs" / "latest_assistant_response.md", latest_assistant_text + "\n")
    _write_turn_outputs(run_dir, transcript)

    timing = {
        "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished_at": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_ms": round(duration_seconds * 1000, 2),
        "total_duration_seconds": round(duration_seconds, 3),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "token_source": "kimi-cli-unavailable",
    }
    write_json(run_dir / "timing.json", timing)

    normalized_transcript = {
        "configuration": resolved_configuration,
        "provider": "kimi-code",
        "model": resolved_model,
        "messages": transcript.get("messages", []),
        "turn_count": len(transcript.get("turns", [])),
        "assistant_response": full_conversation,
        "latest_assistant_response": latest_assistant_text,
        "loaded_files": loaded_files,
        "host_transcript": transcript,
    }
    write_json(run_dir / "transcript.json", normalized_transcript)

    return {
        "run_dir": str(run_dir),
        "configuration": resolved_configuration,
        "provider": "kimi-code",
        "model": resolved_model,
        "duration_seconds": timing["total_duration_seconds"],
        "total_tokens": timing["total_tokens"],
        "output_file": str(run_dir / "outputs" / "final_response.md"),
        "latest_output_file": str(run_dir / "outputs" / "latest_assistant_response.md"),
    }


def execute_iteration(
    iteration_path: str | Path,
    package_path: str | Path,
    *,
    configurations: tuple[str, ...] = ("with_skill", "without_skill"),
    command_runner: CommandRunner | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
    stop_on_error: bool = False,
    skip_completed: bool = False,
) -> dict[str, Any]:
    iteration_dir = Path(iteration_path)
    package_dir = Path(package_path)

    completed_runs: list[dict[str, Any]] = []
    failed_runs: list[dict[str, str]] = []
    skipped_runs: list[dict[str, str]] = []

    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        for configuration in configurations:
            configuration_dir = eval_dir / configuration
            if not configuration_dir.exists():
                continue
            for run_dir in sorted(configuration_dir.glob("run-*")):
                if skip_completed and _run_is_complete(run_dir):
                    skipped_runs.append(
                        {
                            "run_dir": str(run_dir),
                            "configuration": configuration,
                        }
                    )
                    continue
                try:
                    result = execute_run(
                        run_dir,
                        package_dir,
                        configuration=configuration,
                        command_runner=command_runner,
                        model=model,
                        timeout_seconds=timeout_seconds,
                    )
                    completed_runs.append(result)
                except Exception as exc:
                    error_payload = {
                        "run_dir": str(run_dir),
                        "configuration": configuration,
                        "error": str(exc),
                    }
                    write_json(run_dir / "execution_error.json", error_payload)
                    failed_runs.append(error_payload)
                    if stop_on_error:
                        raise

    return {
        "iteration_dir": str(iteration_dir),
        "package_dir": str(package_dir),
        "completed_runs": completed_runs,
        "skipped_runs": skipped_runs,
        "failed_runs": failed_runs,
        "total_runs": len(completed_runs) + len(skipped_runs) + len(failed_runs),
        "successful_runs": len(completed_runs) + len(skipped_runs),
    }


def build_messages(user_prompt: str, skill_text: str | None = None) -> list[dict[str, str]]:
    """Compatibility helper for older tests/docs; execution no longer injects SKILL.md into prompts."""
    if skill_text:
        return [
            {"role": "system", "content": "Kimi Code should read the workspace skill proxy before answering."},
            {"role": "user", "content": user_prompt},
        ]
    return [{"role": "user", "content": user_prompt}]


def _write_skill_proxy(session_dir: Path, package_dir: Path) -> dict[str, str]:
    package_path = package_dir.resolve()
    package_skill_path = package_path / "SKILL.md"
    metadata = extract_frontmatter(package_skill_path.read_text(encoding="utf-8"))
    skills_dir = session_dir / ".kimi" / "skills"
    proxy_skill_dir = skills_dir / package_path.name
    proxy_skill_dir.mkdir(parents=True, exist_ok=True)
    proxy_skill_path = proxy_skill_dir / "SKILL.md"
    proxy_skill_path.write_text(
        render_proxy_skill(package_path, package_skill_path, metadata),
        encoding="utf-8",
    )
    return {
        "skills_dir": str(skills_dir),
        "proxy_skill_path": str(proxy_skill_path),
        "canonical_skill_path": str(package_skill_path),
    }


def _workspace_turn_task_markdown(configuration: str, turn_index: int) -> str:
    if configuration == "with_skill":
        mode_instruction = "\n".join(
            [
                "- The package skill is installed through the workspace-local skill proxy.",
                "- Use the skill when it applies, and read the canonical `SKILL.md` through that proxy instead of relying on prompt-injected skill text.",
                "- Preserve the skill protocol, including direct-result, follow-up, continue, and revise behavior when relevant.",
            ]
        )
    else:
        mode_instruction = "\n".join(
            [
                "- Do not read or use the package skill files.",
                "- Answer as a normal Kimi Code assistant baseline for the same user conversation.",
            ]
        )

    return "\n".join(
        [
            "# Controlled Kimi Eval Turn",
            "",
            f"Turn index: `{turn_index}`",
            f"Configuration: `{configuration}`",
            "",
            "This is a workspace-file task. The terminal reply is only a log line.",
            "",
            "## Inputs",
            "",
            "- Read `inputs/conversation.json`.",
            "- Treat the last `user` message as the current user turn.",
            "- Prior assistant messages are conversation history from earlier scripted turns.",
            "",
            "## Mode Rules",
            "",
            mode_instruction,
            "",
            "## Required Outputs",
            "",
            "- Write the assistant answer for the current turn to `outputs/assistant.md`.",
            "- Write `outputs/run_metadata.json` with at least: `configuration`, `turn_index`, `used_skill`, `notes`.",
            "- Do not put the full answer in the terminal response.",
        ]
    )


def _workspace_turn_contract() -> str:
    return "\n".join(
        [
            "# Output Contract",
            "",
            "Required files:",
            "",
            "1. `outputs/assistant.md`",
            "   - Markdown answer for the latest user turn.",
            "   - This file is the source of truth for grading.",
            "",
            "2. `outputs/run_metadata.json`",
            "   - JSON object.",
            "   - Required keys: `configuration`, `turn_index`, `used_skill`, `notes`.",
            "",
            "Terminal output is ignored except as debug log.",
        ]
    )


def _run_workspace_file_turns(
    turns: list[dict[str, str]],
    *,
    session_dir: Path,
    package_dir: Path,
    configuration: str,
    timeout_seconds: int,
    model: str | None = None,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    session_dir.mkdir(parents=True, exist_ok=True)
    proxy_info = _write_skill_proxy(session_dir, package_dir) if configuration == "with_skill" else {}
    conversation: list[dict[str, str]] = []
    transcript_turns: list[dict[str, Any]] = []
    task_results: list[dict[str, Any]] = []
    stderr_log: list[str] = []

    for turn_index, turn in enumerate(turns, start=1):
        text = str(turn.get("text", "")).strip()
        label = str(turn.get("label", "")).strip()
        conversation.append({"role": "user", "content": text})
        turn_dir = session_dir / f"turn-{turn_index}"
        required_outputs = ["outputs/assistant.md", "outputs/run_metadata.json"]
        write_workspace_task(
            turn_dir,
            task_markdown=_workspace_turn_task_markdown(configuration, turn_index),
            required_outputs=required_outputs,
            contract_markdown=_workspace_turn_contract(),
            inputs={
                "inputs/conversation.json": {
                    "configuration": configuration,
                    "turn_index": turn_index,
                    "turn_label": label,
                    "messages": conversation,
                    "turn_script": turns,
                },
            },
            metadata={
                "runner": "kimi-code",
                "execution_mode": "workspace-file-task",
                "configuration": configuration,
                "turn_index": turn_index,
            },
        )
        task_result = run_kimi_workspace_task(
            turn_dir,
            required_outputs=required_outputs,
            model=model,
            timeout_seconds=timeout_seconds,
            command_runner=command_runner,
            add_dir=package_dir if configuration == "with_skill" else None,
            skills_dir=Path(proxy_info["skills_dir"]) if proxy_info else None,
        )
        assistant_text = read_workspace_text(task_result, "outputs/assistant.md").strip()
        run_metadata = load_workspace_json(task_result, "outputs/run_metadata.json")
        if not isinstance(run_metadata, dict):
            run_metadata = {}
        conversation.append({"role": "assistant", "content": assistant_text})
        if task_result.get("stderr"):
            stderr_log.append(str(task_result["stderr"]))

        transcript_turns.append(
            {
                "turn_index": turn_index,
                "label": label,
                "user_text": text,
                "assistant_text": assistant_text,
                "run_metadata": run_metadata,
                "events": task_result.get("messages", []),
                "command_events": [],
                "warnings": task_result.get("warnings", []),
                "stderr": task_result.get("stderr", ""),
                "task_dir": str(turn_dir),
                "output_file": str(turn_dir / "outputs" / "assistant.md"),
            }
        )
        task_results.append(
            {
                "turn_index": turn_index,
                "task_dir": str(turn_dir),
                "resolved_outputs": task_result.get("resolved_outputs", {}),
                "run_metadata": run_metadata,
                "assistant_text_log": task_result.get("assistant_text", ""),
                "warnings": task_result.get("warnings", []),
                "stderr": task_result.get("stderr", ""),
                "messages": task_result.get("messages", []),
            }
        )

    return {
        "thread_id": None,
        "host_backend": "kimi-code-workspace-task",
        "execution_mode": "workspace-file-task",
        "configuration": configuration,
        "session_dir": str(session_dir),
        "package_dir": str(package_dir),
        "proxy_skill_path": proxy_info.get("proxy_skill_path", ""),
        "canonical_skill_path": proxy_info.get("canonical_skill_path", ""),
        "skills_dir": proxy_info.get("skills_dir", ""),
        "turns": transcript_turns,
        "messages": conversation,
        "task_results": task_results,
        "stderr": stderr_log,
    }
