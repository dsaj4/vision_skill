from __future__ import annotations

import re
from pathlib import Path
from typing import Any


STRUCTURE_DIMENSIONS = [
    ("frontmatter_quality", "Frontmatter Quality", 8),
    ("workflow_clarity", "Workflow Clarity", 15),
    ("boundary_coverage", "Boundary Coverage", 10),
    ("checkpoint_design", "Checkpoint Design", 7),
    ("instruction_specificity", "Instruction Specificity", 15),
    ("resource_integration", "Resource Integration", 5),
]


def _check(check_id: str, passed: bool, detail: str = "") -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": bool(passed),
        "detail": detail,
    }


def _score_from_checks(checks: list[dict[str, Any]]) -> float:
    if not checks:
        return 0.0
    passed = sum(1 for item in checks if item["passed"])
    return round(passed / len(checks) * 10, 2)


def _weighted(score: float, weight: int) -> float:
    return round(score * weight / 10, 2)


def _extract_frontmatter(skill_text: str) -> dict[str, str]:
    if not skill_text.startswith("---"):
        return {}
    end = skill_text.find("\n---", 3)
    if end < 0:
        return {}
    block = skill_text[3:end]
    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _frontmatter_quality(skill_text: str) -> list[dict[str, Any]]:
    frontmatter = _extract_frontmatter(skill_text)
    description = frontmatter.get("description", "")
    return [
        _check("frontmatter_present", bool(frontmatter)),
        _check("name_present", bool(frontmatter.get("name"))),
        _check("description_present", bool(description)),
        _check("description_within_1024_chars", len(description) <= 1024 if description else False),
        _check("description_mentions_use_case", _contains_any(description, ["use", "when", "help", "trigger", "task", "scenario"])),
    ]


def _workflow_clarity(skill_text: str) -> list[dict[str, Any]]:
    step_count = len(re.findall(r"^###\s*(?:Step\s*)?\d+|^###\s*step\s*\d+", skill_text, re.MULTILINE | re.IGNORECASE))
    return [
        _check("has_step_or_workflow_structure", step_count > 0, f"step_count={step_count}"),
        _check("has_input_rule", _contains_any(skill_text, ["input", "missing-info", "minimum viable input", "mvi"])),
        _check("has_output_contract", _contains_any(skill_text, ["output", "output contract", "format", "structure"])),
        _check("has_direct_result_branch", _contains_any(skill_text, ["direct-result", "direct result", "direct mode"])),
        _check("has_staged_or_followup_branch", _contains_any(skill_text, ["staged", "followup", "follow-up", "continue", "checkpoint"])),
    ]


def _boundary_coverage(skill_text: str) -> list[dict[str, Any]]:
    return [
        _check("handles_missing_info", _contains_any(skill_text, ["missing-info", "missing information", "insufficient information", "followup", "follow-up"])),
        _check("handles_revision", _contains_any(skill_text, ["revise", "revision", "redo", "modify"])),
        _check("handles_skip_or_direct_result", _contains_any(skill_text, ["skip", "direct-result", "direct result"])),
        _check("has_boundary_or_safety_clause", _contains_any(skill_text, ["boundary", "guardrail", "risk", "safety", "high-pressure"])),
    ]


def _checkpoint_design(skill_text: str) -> list[dict[str, Any]]:
    pause_hits = len(re.findall(r"checkpoint|pause|confirm|confirmation|continue|revise", skill_text, re.IGNORECASE))
    return [
        _check("has_checkpoint_or_pause_rule", pause_hits > 0, f"checkpoint_hits={pause_hits}"),
        _check("has_continue_branch", _contains_any(skill_text, ["continue"])),
        _check("has_revise_branch", _contains_any(skill_text, ["revise", "revision", "modify"])),
        _check("checkpoint_not_obviously_overused", pause_hits <= 20, f"checkpoint_hits={pause_hits}"),
    ]


def _instruction_specificity(skill_text: str) -> list[dict[str, Any]]:
    return [
        _check("has_concrete_output_shape", _contains_any(skill_text, ["table", "list", "action item", "recommendation", "output", "format", "structure"])),
        _check("has_negative_constraints", _contains_any(skill_text, ["forbid", "forbidden", "do not", "must not", "avoid"])),
        _check("has_examples_or_patterns", _contains_any(skill_text, ["example", "exemplar", "sample", "pattern"])),
        _check("has_fallback_or_handling_rule", _contains_any(skill_text, ["fallback", "otherwise", "if ", "when ", "handle"])),
        _check("not_extremely_short", len(skill_text.strip()) >= 800, f"char_count={len(skill_text.strip())}"),
    ]


def _referenced_resource_paths(skill_text: str) -> list[str]:
    markdown_refs = re.findall(r"\]\(([^)]+)\)", skill_text)
    inline_refs = re.findall(r"`((?:references|assets|scripts)/[^`]+)`", skill_text)
    return [ref for ref in [*markdown_refs, *inline_refs] if not ref.startswith(("http://", "https://", "#"))]


def _resource_integration(skill_text: str, package_dir: Path) -> list[dict[str, Any]]:
    refs = _referenced_resource_paths(skill_text)
    broken = [ref for ref in refs if not (package_dir / ref).exists()]
    references_dir = package_dir / "references"
    assets_dir = package_dir / "assets"
    scripts_dir = package_dir / "scripts"
    has_resource_dir = any(path.exists() for path in (references_dir, assets_dir, scripts_dir))
    return [
        _check("resource_refs_valid", not broken, f"broken={broken}"),
        _check("resource_dirs_present_or_not_required", has_resource_dir or not refs),
        _check("large_materials_can_be_externalized", has_resource_dir or len(skill_text) < 8000, f"char_count={len(skill_text)}"),
    ]


def _dimension(dimension_id: str, name: str, weight: int, checks: list[dict[str, Any]]) -> dict[str, Any]:
    score = _score_from_checks(checks)
    return {
        "id": dimension_id,
        "name": name,
        "source": "darwin-skill",
        "role": "diagnostic-only",
        "weight": weight,
        "score": score,
        "weighted_score": _weighted(score, weight),
        "checks": checks,
    }


def score_skill_structure(package_dir: str | Path) -> dict[str, Any]:
    package_path = Path(package_dir)
    skill_path = package_path / "SKILL.md"
    if not skill_path.exists():
        dimensions = [
            _dimension(dimension_id, name, weight, [_check("skill_missing", False)])
            for dimension_id, name, weight in STRUCTURE_DIMENSIONS
        ]
    else:
        skill_text = skill_path.read_text(encoding="utf-8")
        dimensions = [
            _dimension("frontmatter_quality", "Frontmatter Quality", 8, _frontmatter_quality(skill_text)),
            _dimension("workflow_clarity", "Workflow Clarity", 15, _workflow_clarity(skill_text)),
            _dimension("boundary_coverage", "Boundary Coverage", 10, _boundary_coverage(skill_text)),
            _dimension("checkpoint_design", "Checkpoint Design", 7, _checkpoint_design(skill_text)),
            _dimension("instruction_specificity", "Instruction Specificity", 15, _instruction_specificity(skill_text)),
            _dimension("resource_integration", "Resource Integration", 5, _resource_integration(skill_text, package_path)),
        ]

    total = round(sum(item["weighted_score"] for item in dimensions), 2)
    max_score = sum(weight for _, _, weight in STRUCTURE_DIMENSIONS)
    risks = [
        f"structure.{item['id']}"
        for item in dimensions
        if float(item["score"]) < 6.0
    ]
    return {
        "schema_version": "darwin-structure-v1",
        "source": "darwin-skill dimensions 1-6",
        "role": "diagnostic-only",
        "dimensions": dimensions,
        "weighted_structure_score": {
            "score": total,
            "max_score": max_score,
            "normalized": round(total / max_score, 4) if max_score else 0.0,
            "role": "diagnostic-only",
        },
        "risks": risks,
    }
