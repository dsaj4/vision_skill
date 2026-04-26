from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable


CommandRunner = Callable[[list[str], Path, int | None], dict[str, Any]]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_frontmatter(skill_text: str) -> dict[str, str]:
    if not skill_text.startswith("---"):
        return {"name": "", "description": ""}
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", skill_text, re.DOTALL)
    if not match:
        return {"name": "", "description": ""}
    values: dict[str, str] = {"name": "", "description": ""}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key in values:
            values[key] = raw_value.strip()
    return values


def render_proxy_skill(package_dir: Path, package_skill_path: Path, metadata: dict[str, str]) -> str:
    name = metadata.get("name") or package_dir.name
    description = metadata.get("description") or f"Use this skill whenever the user needs help with {package_dir.name}."
    return "\n".join(
        [
            "---",
            f"name: {name}",
            f"description: {description}",
            "---",
            "",
            "# Host Proxy",
            "",
            "This is a workspace-local proxy used for Kimi Code evaluation.",
            f"Canonical package directory: {package_dir}",
            f"Canonical skill file: {package_skill_path}",
            "",
            "When this skill triggers:",
            f"1. Read the canonical skill file at `{package_skill_path}`.",
            f"2. Follow the canonical package instructions and resources from `{package_dir}`.",
            "3. Do not announce that you are using a proxy skill.",
            "4. Preserve the original protocol behavior from the canonical skill.",
            "",
        ]
    ).strip() + "\n"
