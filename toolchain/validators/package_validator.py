from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


REQUIRED_FILES = [
    "SKILL.md",
    "evals/evals.json",
    "metadata/package.json",
    "metadata/source-map.json",
]

REQUIRED_FRONTMATTER_FIELDS = ["name", "description"]
REQUIRED_PACKAGE_FIELDS = [
    "package_name",
    "skill_name",
    "category",
    "status",
    "version",
    "source_mode",
    "candidate_origin",
]
REQUIRED_SOURCE_MAP_FIELDS = [
    "package_name",
    "source_mode",
    "demo_sources",
    "notes",
]
REQUIRED_EVALS_ROOT_FIELDS = ["skill_name", "evals"]
REQUIRED_EVAL_FIELDS = ["id", "prompt", "expected_output", "files", "expectations"]

FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _issue(code: str, path: str, message: str, severity: str = "error") -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "path": path,
        "message": message,
    }


def _load_json(path: Path, issues: list[dict[str, str]]) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(
            _issue(
                "invalid_json",
                str(path),
                f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}.",
            )
        )
        return None


def _validate_required_fields(
    data: dict[str, Any],
    required_fields: list[str],
    display_path: str,
    issues: list[dict[str, str]],
) -> None:
    for field in required_fields:
        if field not in data:
            issues.append(
                _issue(
                    "missing_json_field",
                    display_path,
                    f"Missing required field '{field}'.",
                )
            )


def _validate_skill_markdown(skill_md_path: Path, issues: list[dict[str, str]]) -> None:
    display_path = "SKILL.md"
    content = skill_md_path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        issues.append(
            _issue(
                "missing_frontmatter",
                display_path,
                "SKILL.md must start with YAML frontmatter.",
            )
        )
        return

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        issues.append(
            _issue(
                "invalid_frontmatter",
                display_path,
                f"Invalid YAML frontmatter: {exc}",
            )
        )
        return

    if not isinstance(frontmatter, dict):
        issues.append(
            _issue(
                "invalid_frontmatter",
                display_path,
                "Frontmatter must parse to a mapping.",
            )
        )
        return

    for field in REQUIRED_FRONTMATTER_FIELDS:
        value = frontmatter.get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append(
                _issue(
                    "missing_frontmatter_field",
                    display_path,
                    f"Frontmatter field '{field}' is required and must be a non-empty string.",
                )
            )


def _validate_package_json(path: Path, issues: list[dict[str, str]]) -> None:
    display_path = "metadata/package.json"
    data = _load_json(path, issues)
    if data is None:
        if issues:
            issues[-1]["path"] = display_path
        return
    if not isinstance(data, dict):
        issues.append(_issue("invalid_json_shape", display_path, "package.json must contain a JSON object."))
        return
    _validate_required_fields(data, REQUIRED_PACKAGE_FIELDS, display_path, issues)


def _validate_source_map_json(path: Path, issues: list[dict[str, str]]) -> None:
    display_path = "metadata/source-map.json"
    data = _load_json(path, issues)
    if data is None:
        if issues:
            issues[-1]["path"] = display_path
        return
    if not isinstance(data, dict):
        issues.append(_issue("invalid_json_shape", display_path, "source-map.json must contain a JSON object."))
        return
    _validate_required_fields(data, REQUIRED_SOURCE_MAP_FIELDS, display_path, issues)


def _validate_evals_json(path: Path, issues: list[dict[str, str]]) -> None:
    display_path = "evals/evals.json"
    data = _load_json(path, issues)
    if data is None:
        if issues:
            issues[-1]["path"] = display_path
        return
    if not isinstance(data, dict):
        issues.append(_issue("invalid_json_shape", display_path, "evals.json must contain a JSON object."))
        return
    _validate_required_fields(data, REQUIRED_EVALS_ROOT_FIELDS, display_path, issues)
    evals = data.get("evals")
    if not isinstance(evals, list):
        issues.append(_issue("invalid_json_field_type", display_path, "'evals' must be a JSON array."))
        return
    for index, eval_item in enumerate(evals):
        if not isinstance(eval_item, dict):
            issues.append(
                _issue(
                    "invalid_json_shape",
                    display_path,
                    f"Eval item at index {index} must be a JSON object.",
                )
            )
            continue
        for field in REQUIRED_EVAL_FIELDS:
            if field not in eval_item:
                issues.append(
                    _issue(
                        "missing_json_field",
                        f"{display_path}#evals[{index}]",
                        f"Missing required field '{field}'.",
                    )
                )


def validate_package(package_path: str | Path) -> dict[str, Any]:
    package_dir = Path(package_path)
    issues: list[dict[str, str]] = []

    if not package_dir.exists():
        issues.append(_issue("missing_package", str(package_dir), "Package path does not exist."))
    elif not package_dir.is_dir():
        issues.append(_issue("invalid_package_path", str(package_dir), "Package path must be a directory."))

    if issues:
        return {
            "package_path": str(package_dir),
            "valid": False,
            "issues": issues,
            "summary": {"errors": len(issues), "warnings": 0},
        }

    for relative_path in REQUIRED_FILES:
        target = package_dir / relative_path
        if not target.exists():
            issues.append(
                _issue(
                    "missing_file",
                    relative_path,
                    f"Required file '{relative_path}' is missing.",
                )
            )

    if issues:
        return {
            "package_path": str(package_dir),
            "valid": False,
            "issues": issues,
            "summary": {"errors": len(issues), "warnings": 0},
        }

    _validate_skill_markdown(package_dir / "SKILL.md", issues)
    _validate_package_json(package_dir / "metadata" / "package.json", issues)
    _validate_source_map_json(package_dir / "metadata" / "source-map.json", issues)
    _validate_evals_json(package_dir / "evals" / "evals.json", issues)

    return {
        "package_path": str(package_dir),
        "valid": len(issues) == 0,
        "issues": issues,
        "summary": {
            "errors": len([issue for issue in issues if issue["severity"] == "error"]),
            "warnings": len([issue for issue in issues if issue["severity"] == "warning"]),
        },
    }
