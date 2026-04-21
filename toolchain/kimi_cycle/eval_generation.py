from __future__ import annotations

from pathlib import Path
from typing import Any

from .context import load_json, load_recent_cycle_context, read_text, write_json, write_text
from .kimi_cli import compact_text, extract_json_object, run_kimi_workspace_task
from .workspace_tasks import prepare_workspace_bundle, to_pretty_json


DEFAULT_SKILL_MAX_CHARS = 12000
DEFAULT_EXAMPLES_MAX_CHARS = 1600


def _normalize_expectations(value: Any, eval_id: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            continue
        expectation_type = str(item.get("type", "contains_any")).strip() or "contains_any"
        if expectation_type not in {"contains_any", "contains_none"}:
            expectation_type = "contains_any"
        keywords = item.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        normalized.append(
            {
                "id": str(item.get("id", f"eval-{eval_id}-exp-{index}")).strip() or f"eval-{eval_id}-exp-{index}",
                "type": expectation_type,
                "text": str(item.get("text", "")).strip(),
                "keywords": [str(keyword).strip() for keyword in keywords if str(keyword).strip()],
            }
        )
    return normalized


def _normalize_host_eval(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    turn_script = value.get("turn_script", [])
    normalized_turn_script: list[Any] = []
    if isinstance(turn_script, list):
        for item in turn_script:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text:
                    normalized_turn_script.append({"text": text})
            else:
                text = str(item).strip()
                if text:
                    normalized_turn_script.append(text)
    result = {
        "enabled": bool(value.get("enabled") or normalized_turn_script),
        "turn_script": normalized_turn_script,
        "expected_trigger": value.get("expected_trigger"),
        "expected_trigger_signals": value.get("expected_trigger_signals", []),
        "expected_protocol_path": str(value.get("expected_protocol_path", "")).strip(),
    }
    if not result["enabled"] and not result["expected_protocol_path"]:
        return {}
    return result


def normalize_generated_eval_set(
    raw_text: str,
    package_meta: dict[str, Any],
    current_root: dict[str, Any],
) -> dict[str, Any]:
    parsed = extract_json_object(raw_text)
    evals = parsed.get("evals")
    if not isinstance(evals, list) or not evals:
        raise ValueError("Generated eval set must contain a non-empty evals list.")

    current_ids = [
        int(item.get("id"))
        for item in current_root.get("evals", [])
        if isinstance(item, dict) and str(item.get("id", "")).strip().isdigit()
    ]
    next_id = max(current_ids or [100]) + 1
    used_ids: set[int] = set()
    normalized_evals: list[dict[str, Any]] = []

    for item in evals:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt", "")).strip()
        if not prompt:
            continue
        raw_id = item.get("id")
        try:
            eval_id = int(raw_id)
        except (TypeError, ValueError):
            eval_id = next_id
            next_id += 1
        while eval_id in used_ids:
            eval_id = next_id
            next_id += 1
        used_ids.add(eval_id)

        normalized_evals.append(
            {
                "id": eval_id,
                "prompt": prompt,
                "expected_output": str(item.get("expected_output", "")).strip(),
                "files": item.get("files", []) if isinstance(item.get("files", []), list) else [],
                "expectations": _normalize_expectations(item.get("expectations", []), eval_id),
                "host_eval": _normalize_host_eval(item.get("host_eval", {})),
            }
        )

    if not normalized_evals:
        raise ValueError("Generated eval set did not contain any usable eval items.")

    return {
        "skill_name": str(parsed.get("skill_name") or current_root.get("skill_name") or package_meta.get("skill_name") or "").strip(),
        "package_name": str(parsed.get("package_name") or current_root.get("package_name") or package_meta.get("package_name") or "").strip(),
        "evals": sorted(normalized_evals, key=lambda item: int(item["id"])),
    }


def _eval_contract_markdown() -> str:
    return "\n".join(
        [
            "# Output Contract",
            "",
            "Write two files under `outputs/` only:",
            "",
            "- `outputs/eval-draft.json`",
            "- `outputs/run-report.json`",
            "",
            "Rules for `outputs/eval-draft.json`:",
            "- must be valid JSON",
            "- root object must contain `skill_name`, `package_name`, and `evals`",
            "- `evals` must be a non-empty array",
            "- each eval must contain `id`, `prompt`, `expected_output`, `files`, `expectations`",
            "- optional `host_eval` is allowed",
            "- keep package identity stable",
            "- prefer 4 to 6 evals",
            "- cover rich-input direct-result, info-missing, staged continue, staged revise, explicit direct-result across the set",
            "",
            "Rules for `outputs/run-report.json`:",
            "- must be valid JSON",
            "- include `task`, `status`, `files_written`, and optional `notes`",
            "",
        ]
    ).strip() + "\n"


def prepare_eval_generation_workspace(
    package_dir: str | Path,
    workspace_dir: str | Path,
    cycle_dir: str | Path,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    cycle_path = Path(cycle_dir) / "eval-generation"
    task_dir = cycle_path / "workspace"

    package_meta = load_json(package_path / "metadata" / "package.json")
    current_evals = load_json(package_path / "evals" / "evals.json")
    skill_text = read_text(package_path / "SKILL.md")
    examples_path = package_path / "references" / "examples.md"
    examples_text = read_text(examples_path) if examples_path.exists() else ""
    recent_context = load_recent_cycle_context(workspace_path)

    packet = {
        "package_meta": {
            "package_name": package_meta.get("package_name", package_path.name),
            "skill_name": package_meta.get("skill_name", package_path.name),
            "category": package_meta.get("category", ""),
        },
        "current_eval_count": len(current_evals.get("evals", [])),
        "current_eval_ids": [item.get("id") for item in current_evals.get("evals", []) if isinstance(item, dict)],
    }

    objective = "\n".join(
        [
            "Revise the package-local eval set for this Vision Skill package.",
            "Make it more discriminative for Kimi Code evaluation while keeping the package identity stable.",
            "Read the provided inputs, contract, and examples before writing outputs.",
        ]
    )

    return prepare_workspace_bundle(
        task_dir,
        task_name="Eval Generation",
        objective=objective,
        input_files={
            "inputs/package-packet.json": to_pretty_json(packet),
            "inputs/recent-context.json": to_pretty_json(recent_context),
            "inputs/current-evals.json": to_pretty_json(current_evals),
            "inputs/current-skill.md": (
                skill_text[:DEFAULT_SKILL_MAX_CHARS] if len(skill_text) > DEFAULT_SKILL_MAX_CHARS else skill_text
            ),
            "inputs/examples.md": (
                examples_text[:DEFAULT_EXAMPLES_MAX_CHARS]
                if len(examples_text) > DEFAULT_EXAMPLES_MAX_CHARS
                else examples_text
            )
            or "# Examples\n\nNo package-local examples were provided.\n",
        },
        contract_files={
            "contracts/output-contract.md": _eval_contract_markdown(),
        },
        example_files={
            "examples/eval-draft.example.json": to_pretty_json(
                {
                    "skill_name": package_meta.get("skill_name", package_path.name),
                    "package_name": package_meta.get("package_name", package_path.name),
                    "evals": [
                        {
                            "id": 101,
                            "prompt": "User request",
                            "expected_output": "Expected response pattern",
                            "files": [],
                            "expectations": [
                                {
                                    "id": "exp-1",
                                    "type": "contains_any",
                                    "text": "Should mention the core result",
                                    "keywords": ["result"],
                                }
                            ],
                            "host_eval": {
                                "enabled": True,
                                "turn_script": ["first turn", "continue"],
                                "expected_trigger": True,
                                "expected_trigger_signals": ["skill read"],
                                "expected_protocol_path": "staged -> continue-loop",
                            },
                        }
                    ],
                }
            ),
            "examples/run-report.example.json": to_pretty_json(
                {
                    "task": "eval-generation",
                    "status": "completed",
                    "files_written": ["outputs/eval-draft.json", "outputs/run-report.json"],
                    "notes": "Kept package identity stable and refreshed the eval mix.",
                }
            ),
        },
        required_outputs=["outputs/eval-draft.json", "outputs/run-report.json"],
    )


def _repair_eval_output_in_workspace(
    task_dir: Path,
    error_text: str,
    *,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    prompt = "\n".join(
        [
            "Read `task.md`, `workspace-manifest.json`, `contracts/output-contract.md`, and `outputs/eval-draft.json`.",
            "Fix `outputs/eval-draft.json` in place so it becomes valid JSON and follows the contract.",
            "Preserve semantics and eval intent as much as possible.",
            "Update `outputs/run-report.json` if needed.",
            "Return one short completion note.",
            "",
            "Repair reason:",
            compact_text(error_text, 2400),
        ]
    )
    write_text(task_dir / "repair-request.md", prompt)
    return run_kimi_workspace_task(
        prompt,
        task_dir,
        required_outputs=["outputs/eval-draft.json", "outputs/run-report.json"],
        model=model,
        timeout_seconds=timeout_seconds,
    )


def generate_eval_draft(
    package_dir: str | Path,
    workspace_dir: str | Path,
    cycle_dir: str | Path,
    *,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    cycle_path = Path(cycle_dir) / "eval-generation"
    workspace_bundle = prepare_eval_generation_workspace(package_path, workspace_dir, cycle_dir)
    write_text(cycle_path / "prompt.txt", workspace_bundle["task_prompt"])

    kimi_result = run_kimi_workspace_task(
        workspace_bundle["task_prompt"],
        workspace_bundle["task_dir"],
        required_outputs=workspace_bundle["required_outputs"],
        model=model,
        timeout_seconds=timeout_seconds,
    )
    write_text(cycle_path / "assistant-message.txt", kimi_result["assistant_text"])
    write_text(cycle_path / "raw-response.txt", kimi_result["stdout"])
    write_text(cycle_path / "stderr.txt", kimi_result["stderr"])

    package_meta = load_json(package_path / "metadata" / "package.json")
    current_evals = load_json(package_path / "evals" / "evals.json")
    draft_output_path = Path(kimi_result["resolved_outputs"]["outputs/eval-draft.json"])
    raw_text = read_text(draft_output_path)
    repair_used = False
    try:
        generated = normalize_generated_eval_set(
            raw_text,
            package_meta,
            current_evals,
        )
    except Exception as exc:
        repair_result = _repair_eval_output_in_workspace(
            Path(workspace_bundle["task_dir"]),
            str(exc),
            model=model,
            timeout_seconds=timeout_seconds,
        )
        write_text(cycle_path / "repair-response.txt", repair_result["assistant_text"])
        repaired_text = read_text(Path(repair_result["resolved_outputs"]["outputs/eval-draft.json"]))
        generated = normalize_generated_eval_set(
            repaired_text,
            package_meta,
            current_evals,
        )
        repair_used = True
    write_json(draft_output_path, generated)
    write_json(
        cycle_path / "result.json",
        {
            "generator": "kimi-cli",
            "package_name": package_meta.get("package_name", package_path.name),
            "output_path": str(draft_output_path),
            "generated_eval_count": len(generated["evals"]),
            "model": kimi_result["model"],
            "repair_used": repair_used,
            "workspace_task_dir": workspace_bundle["task_dir"],
        },
    )
    return {
        "cycle_dir": str(cycle_path),
        "draft_path": str(draft_output_path),
        "result_path": str(cycle_path / "result.json"),
        "generated_eval_count": len(generated["evals"]),
    }


def apply_eval_draft(
    package_dir: str | Path,
    draft_path: str | Path,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    draft = load_json(Path(draft_path))
    output_path = package_path / "evals" / "evals.json"
    write_json(output_path, draft)
    return {
        "applied": True,
        "output_path": str(output_path),
        "eval_count": len(draft.get("evals", [])),
    }
