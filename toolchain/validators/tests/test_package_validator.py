from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.validators.package_validator import validate_package


REQUIRED_FRONTMATTER = """---
name: Example Skill
description: Example description
---

# Example
"""


def write_valid_package(base: Path) -> Path:
    package_dir = base / "example-package"
    (package_dir / "evals").mkdir(parents=True)
    (package_dir / "metadata").mkdir(parents=True)

    (package_dir / "SKILL.md").write_text(REQUIRED_FRONTMATTER, encoding="utf-8")
    (package_dir / "evals" / "evals.json").write_text(
        json.dumps(
            {
                "skill_name": "Example Skill",
                "evals": [
                    {
                        "id": 1,
                        "prompt": "Test prompt",
                        "expected_output": "Expected output description",
                        "files": [],
                        "expectations": ["Output follows the expected structure."],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "metadata" / "package.json").write_text(
        json.dumps(
            {
                "package_name": "example-package",
                "skill_name": "Example Skill",
                "category": "strategy",
                "status": "candidate",
                "version": "0.1.0",
                "source_mode": "demo-only",
                "candidate_origin": "demo-migration",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "metadata" / "source-map.json").write_text(
        json.dumps(
            {
                "package_name": "example-package",
                "source_mode": "demo-only",
                "demo_sources": [
                    {
                        "kind": "skill_markdown",
                        "path": "E:\\demo\\example\\SKILL.md",
                        "note": "Seeded from demo.",
                    }
                ],
                "notes": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return package_dir


def test_validate_package_accepts_current_swot_package() -> None:
    package_dir = Path(r"E:\Project\vision-lab\vision-skill\packages\swot-analysis")

    result = validate_package(package_dir)

    assert result["valid"] is True
    assert result["summary"]["errors"] == 0


def test_validate_package_rejects_missing_required_file(tmp_path: Path) -> None:
    package_dir = write_valid_package(tmp_path)
    (package_dir / "metadata" / "source-map.json").unlink()

    result = validate_package(package_dir)

    assert result["valid"] is False
    assert "metadata/source-map.json" in result["issues"][0]["path"]


def test_validate_package_rejects_invalid_json(tmp_path: Path) -> None:
    package_dir = write_valid_package(tmp_path)
    (package_dir / "evals" / "evals.json").write_text("{ bad json", encoding="utf-8")

    result = validate_package(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "invalid_json" for issue in result["issues"])


def test_validate_package_rejects_missing_frontmatter_description(tmp_path: Path) -> None:
    package_dir = write_valid_package(tmp_path)
    (package_dir / "SKILL.md").write_text(
        """---
name: Example Skill
---

# Example
""",
        encoding="utf-8",
    )

    result = validate_package(package_dir)

    assert result["valid"] is False
    assert any(issue["code"] == "missing_frontmatter_field" for issue in result["issues"])
