from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from toolchain.validators.package_validator import validate_package
from toolchain.validators.protocol_validator import validate_protocol

from .context import compact_json_block, load_json, load_recent_cycle_context, read_text, write_json, write_text
from .kimi_cli import extract_markdown_document, run_kimi_prompt


DEFAULT_SKILL_MAX_CHARS = 14000
DEFAULT_EXAMPLES_MAX_CHARS = 2000

GUIDE_SUMMARY = "\n".join(
    [
        "- Keep valid YAML frontmatter with name and description.",
        "- Prefer direct-result when user information is already rich enough.",
        "- Ask only for missing information when input is vague.",
        "- Use staged checkpoints only when the user clearly wants co-creation.",
        "- Make outputs actionable and specific, not framework theater.",
        "- Keep the tone natural. Avoid mechanical meta-language.",
        "- Do not repeat the same rule in multiple sections.",
        "- Keep the final skill compact enough for repeated evaluation rounds.",
    ]
)


def normalize_rewritten_skill(raw_text: str) -> str:
    normalized = extract_markdown_document(raw_text).lstrip("\ufeff").strip()
    if not normalized.startswith("---"):
        match = re.search(r"(?m)^---\s*$", normalized)
        if match:
            normalized = normalized[match.start() :].strip()
    if normalized.startswith("---"):
        second_delimiter = re.search(r"(?m)^---\s*$", normalized[4:])
        if second_delimiter is None:
            heading_match = re.search(r"(?m)^#\s+", normalized)
            if heading_match:
                normalized = normalized[: heading_match.start()].rstrip() + "\n---\n\n" + normalized[heading_match.start() :].lstrip()
    if not normalized.startswith("---"):
        raise ValueError("Rewritten skill must start with YAML frontmatter.")
    if "\n# " not in normalized:
        raise ValueError("Rewritten skill must contain a markdown title.")
    return normalized.strip() + "\n"


def _load_demo_skill_paths(package_dir: Path) -> list[Path]:
    source_map = load_json(package_dir / "metadata" / "source-map.json")
    paths: list[Path] = []
    for item in source_map.get("demo_sources", []):
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "skill_markdown":
            continue
        path_text = str(item.get("path", "")).strip()
        if path_text:
            paths.append(Path(path_text))
    return paths


def validate_rewritten_skill(package_dir: str | Path, rewritten_skill: str) -> dict[str, Any]:
    package_path = Path(package_dir)
    with tempfile.TemporaryDirectory(prefix="vision-skill-kimi-validate-") as temp_dir:
        temp_package = Path(temp_dir) / package_path.name
        shutil.copytree(package_path, temp_package)
        (temp_package / "SKILL.md").write_text(rewritten_skill, encoding="utf-8")
        package_result = validate_package(temp_package)
        protocol_result = validate_protocol(temp_package)
        valid = bool(package_result["valid"] and protocol_result["valid"])
        return {
            "valid": valid,
            "package_validator": package_result,
            "protocol_validator": protocol_result,
        }


def build_skill_rewrite_prompt(
    package_dir: str | Path,
    workspace_dir: str | Path,
) -> str:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    package_meta = load_json(package_path / "metadata" / "package.json")
    current_skill = read_text(package_path / "SKILL.md")
    current_evals = load_json(package_path / "evals" / "evals.json")
    recent_context = load_recent_cycle_context(workspace_path)
    examples_path = package_path / "references" / "examples.md"
    examples_text = read_text(examples_path) if examples_path.exists() else ""

    packet = {
        "package_meta": {
            "package_name": package_meta.get("package_name", package_path.name),
            "skill_name": package_meta.get("skill_name", package_path.name),
            "category": package_meta.get("category", ""),
        },
        "current_eval_ids": [item.get("id") for item in current_evals.get("evals", []) if isinstance(item, dict)],
        "recent_context": recent_context,
    }

    return "\n".join(
        [
            "You are revising one Vision Skill package for Codex.",
            "Codex is the controller. Output only the final full SKILL.md markdown.",
            "Do not explain your changes. Do not add markdown fences.",
            "Keep the package identity stable. Improve user value, direct-result quality, and protocol fit using the recent eval findings.",
            "The rewritten skill must remain concise, readable, and executable.",
            "Preserve a valid YAML frontmatter with name and description.",
            "",
            "Package packet:",
            compact_json_block(packet, 12000),
            "",
            "Optimization guide summary:",
            GUIDE_SUMMARY,
            "",
            "Current SKILL.md:",
            current_skill[:DEFAULT_SKILL_MAX_CHARS] if len(current_skill) > DEFAULT_SKILL_MAX_CHARS else current_skill,
            "",
            "Current examples reference:",
            examples_text[:DEFAULT_EXAMPLES_MAX_CHARS] if len(examples_text) > DEFAULT_EXAMPLES_MAX_CHARS else examples_text,
        ]
    )


def generate_skill_rewrite(
    package_dir: str | Path,
    workspace_dir: str | Path,
    cycle_dir: str | Path,
    *,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    cycle_path = Path(cycle_dir) / "skill-rewrite"
    generated_skill_path = cycle_path / "SKILL.generated.md"
    validation_path = cycle_path / "validation.json"
    prompt = build_skill_rewrite_prompt(package_path, workspace_dir)
    write_text(cycle_path / "prompt.txt", prompt)

    kimi_result = run_kimi_prompt(
        prompt,
        cycle_path / "run",
        model=model,
        timeout_seconds=timeout_seconds,
    )
    raw_output = kimi_result["assistant_text"] or kimi_result["stdout"]
    write_text(cycle_path / "raw-response.md", raw_output)

    try:
        rewritten_skill = normalize_rewritten_skill(raw_output)
        write_text(generated_skill_path, rewritten_skill)
        validation = validate_rewritten_skill(package_path, rewritten_skill)
    except Exception as exc:
        write_text(generated_skill_path, raw_output)
        validation = {
            "valid": False,
            "normalization_error": str(exc),
            "package_validator": {
                "valid": False,
                "issues": [],
                "summary": {"errors": 0, "warnings": 0},
            },
            "protocol_validator": {
                "valid": False,
                "issues": [],
                "summary": {"errors": 0, "warnings": 0},
            },
        }
    write_json(validation_path, validation)

    return {
        "cycle_dir": str(cycle_path),
        "generated_skill_path": str(generated_skill_path),
        "validation_path": str(validation_path),
        "valid": bool(validation["valid"]),
    }


def apply_skill_rewrite(
    package_dir: str | Path,
    generated_skill_path: str | Path,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    generated_path = Path(generated_skill_path)
    content = read_text(generated_path)
    applied_paths: list[str] = []

    package_skill_path = package_path / "SKILL.md"
    write_text(package_skill_path, content)
    applied_paths.append(str(package_skill_path))

    for demo_path in _load_demo_skill_paths(package_path):
        demo_path.parent.mkdir(parents=True, exist_ok=True)
        write_text(demo_path, content)
        applied_paths.append(str(demo_path))

    return {
        "applied": True,
        "applied_paths": applied_paths,
        "package_skill_path": str(package_skill_path),
    }
