from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from toolchain.validators.package_validator import validate_package
from toolchain.validators.protocol_validator import validate_protocol

from .context import load_json, load_recent_cycle_context, read_text, write_json, write_text
from .kimi_cli import extract_markdown_document, run_kimi_workspace_task
from .workspace_tasks import prepare_workspace_bundle, to_pretty_json


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


def _skill_contract_markdown() -> str:
    return "\n".join(
        [
            "# Output Contract",
            "",
            "Write two files under `outputs/` only:",
            "",
            "- `outputs/SKILL.generated.md`",
            "- `outputs/run-report.json`",
            "",
            "Rules for `outputs/SKILL.generated.md`:",
            "- must be a full markdown document",
            "- must begin with valid YAML frontmatter",
            "- frontmatter must contain `name` and `description`",
            "- must contain a markdown title",
            "- keep the package identity stable",
            "- improve direct-result quality, protocol fit, and user value using the provided eval context",
            "- keep the skill concise and executable",
            "",
            "Rules for `outputs/run-report.json`:",
            "- must be valid JSON",
            "- include `task`, `status`, `files_written`, and optional `notes`",
            "",
        ]
    ).strip() + "\n"


def prepare_skill_rewrite_workspace(
    package_dir: str | Path,
    workspace_dir: str | Path,
    cycle_dir: str | Path,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    workspace_path = Path(workspace_dir)
    cycle_path = Path(cycle_dir) / "skill-rewrite"
    task_dir = cycle_path / "workspace"

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
    }

    objective = "\n".join(
        [
            "Rewrite the package skill as a controlled workspace edit task.",
            "Use the recent eval findings to improve direct-result quality, protocol fit, and overall usefulness.",
            "Read the provided inputs, contract, and examples before writing outputs.",
        ]
    )

    return prepare_workspace_bundle(
        task_dir,
        task_name="Skill Rewrite",
        objective=objective,
        input_files={
            "inputs/package-packet.json": to_pretty_json(packet),
            "inputs/recent-context.json": to_pretty_json(recent_context),
            "inputs/current-skill.md": (
                current_skill[:DEFAULT_SKILL_MAX_CHARS] if len(current_skill) > DEFAULT_SKILL_MAX_CHARS else current_skill
            ),
            "inputs/examples.md": (
                examples_text[:DEFAULT_EXAMPLES_MAX_CHARS]
                if len(examples_text) > DEFAULT_EXAMPLES_MAX_CHARS
                else examples_text
            )
            or "# Examples\n\nNo package-local examples were provided.\n",
        },
        contract_files={
            "contracts/output-contract.md": _skill_contract_markdown(),
        },
        example_files={
            "examples/SKILL.example.md": "\n".join(
                [
                    "---",
                    "name: example-skill",
                    "description: Use when an example is needed.",
                    "---",
                    "",
                    "# Example Skill",
                    "",
                    "## Core Task",
                    "",
                    "Give a useful direct result when the input is already rich enough.",
                    "",
                    "## Interaction Modes",
                    "",
                    "- Direct result when context is sufficient",
                    "- Ask only for missing information when context is thin",
                    "- Use staged checkpoints only for real co-creation",
                    "",
                ]
            ).strip()
            + "\n",
            "examples/run-report.example.json": to_pretty_json(
                {
                    "task": "skill-rewrite",
                    "status": "completed",
                    "files_written": ["outputs/SKILL.generated.md", "outputs/run-report.json"],
                    "notes": "Rewritten skill keeps identity stable and improves protocol fit.",
                }
            ),
        },
        required_outputs=["outputs/SKILL.generated.md", "outputs/run-report.json"],
    )


def _repair_skill_output_in_workspace(
    task_dir: Path,
    error_text: str,
    *,
    model: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    prompt = "\n".join(
        [
            "Read `task.md`, `workspace-manifest.json`, `contracts/output-contract.md`, and `outputs/SKILL.generated.md`.",
            "Fix `outputs/SKILL.generated.md` in place so it satisfies the contract and the validation feedback.",
            "Update `outputs/run-report.json` if needed.",
            "Return one short completion note.",
            "",
            "Validation feedback:",
            error_text,
        ]
    )
    write_text(task_dir / "repair-request.md", prompt)
    return run_kimi_workspace_task(
        prompt,
        task_dir,
        required_outputs=["outputs/SKILL.generated.md", "outputs/run-report.json"],
        model=model,
        timeout_seconds=timeout_seconds,
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
    validation_path = cycle_path / "validation.json"
    workspace_bundle = prepare_skill_rewrite_workspace(package_path, workspace_dir, cycle_dir)
    generated_skill_path = Path(workspace_bundle["task_dir"]) / "outputs" / "SKILL.generated.md"
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

    raw_output = read_text(generated_skill_path)
    write_text(cycle_path / "raw-response.md", raw_output)

    normalization_error: str | None = None
    repair_used = False
    try:
        rewritten_skill = normalize_rewritten_skill(raw_output)
        write_text(generated_skill_path, rewritten_skill)
        validation = validate_rewritten_skill(package_path, rewritten_skill)
        if not validation["valid"]:
            raise ValueError(
                "Validation failed: "
                f"package errors={validation['package_validator']['summary']['errors']}, "
                f"protocol errors={validation['protocol_validator']['summary']['errors']}"
            )
    except Exception as exc:
        normalization_error = str(exc)
        repair_result = _repair_skill_output_in_workspace(
            Path(workspace_bundle["task_dir"]),
            normalization_error,
            model=model,
            timeout_seconds=timeout_seconds,
        )
        write_text(cycle_path / "repair-response.txt", repair_result["assistant_text"])
        repaired_output = read_text(generated_skill_path)
        write_text(cycle_path / "repaired-response.md", repaired_output)
        repair_used = True
        try:
            rewritten_skill = normalize_rewritten_skill(repaired_output)
            write_text(generated_skill_path, rewritten_skill)
            validation = validate_rewritten_skill(package_path, rewritten_skill)
        except Exception as repair_exc:
            normalization_error = str(repair_exc)
            validation = {
                "valid": False,
                "normalization_error": normalization_error,
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
    if normalization_error and "normalization_error" not in validation:
        validation["normalization_error"] = normalization_error
    validation["repair_used"] = repair_used
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
