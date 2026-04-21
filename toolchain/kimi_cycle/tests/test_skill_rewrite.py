from __future__ import annotations

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.kimi_cycle.skill_rewrite import apply_skill_rewrite, normalize_rewritten_skill


def test_normalize_rewritten_skill_accepts_fenced_markdown() -> None:
    raw = """```markdown
---
name: demo-skill
description: Use when testing.
---

# Demo Skill
```"""
    normalized = normalize_rewritten_skill(raw)
    assert normalized.startswith("---")
    assert "# Demo Skill" in normalized


def test_normalize_rewritten_skill_repairs_missing_frontmatter_closer() -> None:
    raw = """---
name: demo-skill
description: Use when testing.

# Demo Skill
"""
    normalized = normalize_rewritten_skill(raw)
    assert normalized.startswith("---")
    assert "\n---\n\n# Demo Skill" in normalized


def test_apply_skill_rewrite_updates_package_and_demo(tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "SKILL.md").write_text("---\nname: old\ndescription: old\n---\n\n# Old\n", encoding="utf-8")
    demo_path = tmp_path / "demo" / "SKILL.md"
    source_map = {
        "package_name": "demo-package",
        "source_mode": "demo-only",
        "demo_sources": [{"kind": "skill_markdown", "path": str(demo_path)}],
        "supporting_sources": [],
        "notes": [],
    }
    (package_dir / "metadata" / "source-map.json").write_text(json.dumps(source_map, ensure_ascii=False, indent=2), encoding="utf-8")

    generated_path = tmp_path / "generated.md"
    generated_content = "---\nname: new-skill\ndescription: Use when better.\n---\n\n# New Skill\n"
    generated_path.write_text(generated_content, encoding="utf-8")

    result = apply_skill_rewrite(package_dir, generated_path)

    assert result["applied"] is True
    assert (package_dir / "SKILL.md").read_text(encoding="utf-8") == generated_content
    assert demo_path.read_text(encoding="utf-8") == generated_content
