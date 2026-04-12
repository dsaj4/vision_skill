from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 180

Sender = Callable[[dict[str, Any], str, str, int], dict[str, Any]]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_model(model: str | None) -> str:
    return (
        model
        or os.getenv("DASHSCOPE_MODEL")
        or os.getenv("QWEN_MODEL")
        or "qwen-plus"
    )


def _resolve_endpoint(endpoint: str | None) -> str:
    if endpoint:
        return endpoint
    base_url = os.getenv("DASHSCOPE_BASE_URL", "").rstrip("/")
    if base_url:
        return f"{base_url}/chat/completions"
    return DEFAULT_ENDPOINT


def _resolve_timeout(timeout_seconds: int | None) -> int:
    if timeout_seconds is not None:
        return timeout_seconds
    value = os.getenv("DASHSCOPE_TIMEOUT_SECONDS")
    if value and value.isdigit():
        return int(value)
    return DEFAULT_TIMEOUT_SECONDS


def _resolve_api_key(api_key: str | None) -> str:
    resolved = api_key or os.getenv("DASHSCOPE_API_KEY")
    if not resolved:
        raise RuntimeError("Missing DASHSCOPE_API_KEY and no api_key override was provided.")
    return resolved


def _load_skill_text(package_dir: Path) -> str:
    return (package_dir / "SKILL.md").read_text(encoding="utf-8")


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


def build_messages(user_prompt: str, skill_text: str | None = None) -> list[dict[str, str]]:
    if skill_text:
        system_prompt = "\n".join(
            [
                "You are executing a skill package evaluation run.",
                "Treat the following SKILL.md as the governing workflow and behavior contract for this task.",
                "Follow the skill instructions closely, including any direct-result or staged interaction logic inside the skill itself.",
                "",
                "<SKILL_MD>",
                skill_text,
                "</SKILL_MD>",
            ]
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    return [{"role": "user", "content": user_prompt}]


def _extract_assistant_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content)


def _post_chat_completion(payload: dict[str, Any], endpoint: str, api_key: str, timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DashScope request failed with {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DashScope request failed: {exc.reason}") from exc


def execute_run(
    run_path: str | Path,
    package_path: str | Path,
    configuration: str | None = None,
    *,
    sender: Sender | None = None,
    api_key: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_path)
    package_dir = Path(package_path)
    eval_dir = run_dir.parent.parent
    iteration_dir = eval_dir.parent
    resolved_configuration = configuration or run_dir.parent.name

    eval_metadata = _load_json(eval_dir / "eval_metadata.json")
    file_context, loaded_files = _render_file_context(
        [str(item) for item in eval_metadata.get("files", [])],
        package_dir,
        iteration_dir,
    )
    user_prompt = eval_metadata.get("prompt", "")
    if file_context:
        user_prompt = f"{user_prompt}\n\n{file_context}"

    skill_text = _load_skill_text(package_dir) if resolved_configuration == "with_skill" else None
    messages = build_messages(user_prompt, skill_text=skill_text)

    resolved_model = _resolve_model(model)
    resolved_endpoint = _resolve_endpoint(endpoint)
    resolved_timeout = _resolve_timeout(timeout_seconds)
    resolved_api_key = _resolve_api_key(api_key)
    request_payload = {
        "model": resolved_model,
        "messages": messages,
    }

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "request.json", request_payload)

    started_at = datetime.now(timezone.utc)
    start = time.perf_counter()
    response = (sender or _post_chat_completion)(
        request_payload,
        resolved_endpoint,
        resolved_api_key,
        resolved_timeout,
    )
    duration_seconds = time.perf_counter() - start
    finished_at = datetime.now(timezone.utc)

    _write_json(run_dir / "raw_response.json", response)

    assistant_text = _extract_assistant_text(response)
    (run_dir / "outputs" / "final_response.md").write_text(assistant_text, encoding="utf-8")

    usage = response.get("usage", {})
    timing = {
        "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished_at": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_ms": round(duration_seconds * 1000, 2),
        "total_duration_seconds": round(duration_seconds, 3),
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }
    _write_json(run_dir / "timing.json", timing)

    transcript = {
        "configuration": resolved_configuration,
        "model": resolved_model,
        "endpoint": resolved_endpoint,
        "messages": messages,
        "assistant_response": assistant_text,
        "loaded_files": loaded_files,
    }
    _write_json(run_dir / "transcript.json", transcript)

    return {
        "run_dir": str(run_dir),
        "configuration": resolved_configuration,
        "model": resolved_model,
        "endpoint": resolved_endpoint,
        "duration_seconds": timing["total_duration_seconds"],
        "total_tokens": timing["total_tokens"],
        "output_file": str(run_dir / "outputs" / "final_response.md"),
    }


def execute_iteration(
    iteration_path: str | Path,
    package_path: str | Path,
    *,
    configurations: tuple[str, ...] = ("with_skill", "without_skill"),
    sender: Sender | None = None,
    api_key: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    timeout_seconds: int | None = None,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    iteration_dir = Path(iteration_path)
    package_dir = Path(package_path)

    completed_runs: list[dict[str, Any]] = []
    failed_runs: list[dict[str, str]] = []

    for eval_dir in sorted(iteration_dir.glob("eval-*")):
        for configuration in configurations:
            configuration_dir = eval_dir / configuration
            if not configuration_dir.exists():
                continue
            for run_dir in sorted(configuration_dir.glob("run-*")):
                try:
                    result = execute_run(
                        run_dir,
                        package_dir,
                        configuration=configuration,
                        sender=sender,
                        api_key=api_key,
                        model=model,
                        endpoint=endpoint,
                        timeout_seconds=timeout_seconds,
                    )
                    completed_runs.append(result)
                except Exception as exc:
                    error_payload = {
                        "run_dir": str(run_dir),
                        "configuration": configuration,
                        "error": str(exc),
                    }
                    _write_json(run_dir / "execution_error.json", error_payload)
                    failed_runs.append(error_payload)
                    if stop_on_error:
                        raise

    return {
        "iteration_dir": str(iteration_dir),
        "package_dir": str(package_dir),
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "total_runs": len(completed_runs) + len(failed_runs),
        "successful_runs": len(completed_runs),
    }
