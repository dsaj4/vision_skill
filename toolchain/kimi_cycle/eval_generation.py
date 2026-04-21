from __future__ import annotations

from pathlib import Path
from typing import Any

from .context import compact_json_block, load_json, load_recent_cycle_context, read_text, write_json, write_text
from .kimi_cli import compact_text, extract_json_object, run_kimi_prompt


DEFAULT_SKILL_MAX_CHARS = 12000


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


def build_eval_generation_prompt(
    package_dir: str | Path,
    workspace_dir: str | Path,
) -> str:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    package_meta = load_json(package_path / "metadata" / "package.json")
    current_evals = load_json(package_path / "evals" / "evals.json")
    skill_text = read_text(package_path / "SKILL.md")
    recent_context = load_recent_cycle_context(workspace_path)

    packet = {
        "package_meta": {
            "package_name": package_meta.get("package_name", package_path.name),
            "skill_name": package_meta.get("skill_name", package_path.name),
            "category": package_meta.get("category", ""),
        },
        "current_eval_count": len(current_evals.get("evals", [])),
        "current_evals": current_evals.get("evals", []),
        "recent_context": recent_context,
    }

    return "\n".join(
        [
            "You are helping Codex generate a stronger eval set for one Vision Skill package.",
            "Codex is the controller. Return JSON only. Do not use markdown fences.",
            "Revise the package-local eval set so it is more discriminative when the skill is tested with Kimi Code.",
            "Keep package_name and skill_name unchanged.",
            "Prefer 4 to 6 evals.",
            "Cover these paths across the whole set: rich-input direct-result, info-missing, staged continue, staged revise, explicit direct-result.",
            "Preserve strong existing eval ids when possible. Add new ids only when needed.",
            "Each eval must contain: id, prompt, expected_output, files, expectations, optional host_eval.",
            "Use short keyword-based expectations. expectation.type must be contains_any or contains_none.",
            "Only include host_eval when multi-turn behavior needs to be verified.",
            "",
            "Return this exact JSON shape:",
            '{"skill_name":"","package_name":"","evals":[{"id":101,"prompt":"","expected_output":"","files":[],"expectations":[{"id":"","type":"contains_any","text":"","keywords":[""]}],"host_eval":{"enabled":true,"turn_script":[""],"expected_trigger":true,"expected_trigger_signals":[""],"expected_protocol_path":""}}]}',
            "",
            "Current package packet:",
            compact_json_block(packet, 16000),
            "",
            "Current SKILL.md:",
            skill_text[:DEFAULT_SKILL_MAX_CHARS] if len(skill_text) > DEFAULT_SKILL_MAX_CHARS else skill_text,
        ]
    )


def _repair_eval_json(
    raw_text: str,
    cycle_path: Path,
    *,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> str:
    prompt = "\n".join(
        [
            "You are fixing invalid JSON.",
            "Do not change semantics, ids, or field names.",
            "Only repair JSON syntax such as quotes, escaping, commas, and brackets.",
            "Return valid JSON only. Do not use markdown fences.",
            "",
            "Invalid JSON:",
            compact_text(raw_text, 18000),
        ]
    )
    write_text(cycle_path / "repair-prompt.txt", prompt)
    repair_result = run_kimi_prompt(
        prompt,
        cycle_path / "repair-run",
        model=model,
        timeout_seconds=timeout_seconds,
    )
    repaired_text = repair_result["assistant_text"] or repair_result["stdout"]
    write_text(cycle_path / "repair-response.txt", repaired_text)
    return repaired_text


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
    prompt = build_eval_generation_prompt(package_path, workspace_dir)
    write_text(cycle_path / "prompt.txt", prompt)

    kimi_result = run_kimi_prompt(
        prompt,
        cycle_path / "run",
        model=model,
        timeout_seconds=timeout_seconds,
    )
    write_text(cycle_path / "raw-response.txt", kimi_result["assistant_text"] or kimi_result["stdout"])

    package_meta = load_json(package_path / "metadata" / "package.json")
    current_evals = load_json(package_path / "evals" / "evals.json")
    raw_text = kimi_result["assistant_text"] or kimi_result["stdout"]
    repair_used = False
    try:
        generated = normalize_generated_eval_set(
            raw_text,
            package_meta,
            current_evals,
        )
    except Exception:
        repaired_text = _repair_eval_json(
            raw_text,
            cycle_path,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        generated = normalize_generated_eval_set(
            repaired_text,
            package_meta,
            current_evals,
        )
        repair_used = True
    write_json(cycle_path / "eval-draft.json", generated)
    write_json(
        cycle_path / "result.json",
        {
            "generator": "kimi-cli",
            "package_name": package_meta.get("package_name", package_path.name),
            "output_path": str(cycle_path / "eval-draft.json"),
            "generated_eval_count": len(generated["evals"]),
            "model": kimi_result["model"],
            "repair_used": repair_used,
        },
    )
    return {
        "cycle_dir": str(cycle_path),
        "draft_path": str(cycle_path / "eval-draft.json"),
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
