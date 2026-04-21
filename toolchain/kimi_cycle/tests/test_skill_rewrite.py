from __future__ import annotations

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.kimi_cycle.skill_rewrite import (
    apply_skill_rewrite,
    generate_skill_rewrite,
    normalize_rewritten_skill,
    prepare_skill_rewrite_workspace,
)


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


def test_prepare_skill_rewrite_workspace_writes_manifest_and_examples(tmp_path: Path) -> None:
    package_dir = tmp_path / "packages" / "golden-circle"
    workspace_dir = tmp_path / "workspace"
    cycle_dir = workspace_dir / "cycles" / "kimi-cycle-test"
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "evals").mkdir(parents=True)
    (package_dir / "references").mkdir(parents=True)

    (package_dir / "metadata" / "package.json").write_text(
        json.dumps(
            {
                "package_name": "golden-circle",
                "skill_name": "Golden Circle",
                "category": "thinking",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "evals" / "evals.json").write_text(
        json.dumps({"skill_name": "Golden Circle", "evals": [{"id": 101}]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (package_dir / "SKILL.md").write_text("---\nname: golden-circle\ndescription: Use when needed.\n---\n\n# Golden Circle\n", encoding="utf-8")
    (package_dir / "references" / "examples.md").write_text("# Examples\n\n- staged example", encoding="utf-8")

    result = prepare_skill_rewrite_workspace(package_dir, workspace_dir, cycle_dir)

    task_dir = Path(result["task_dir"])
    assert (task_dir / "task.md").exists()
    assert (task_dir / "workspace-manifest.json").exists()
    assert (task_dir / "inputs" / "package-packet.json").exists()
    assert (task_dir / "inputs" / "recent-context.json").exists()
    assert (task_dir / "inputs" / "current-skill.md").exists()
    assert (task_dir / "inputs" / "examples.md").exists()
    assert (task_dir / "contracts" / "output-contract.md").exists()
    assert (task_dir / "examples" / "SKILL.example.md").exists()
    assert (task_dir / "examples" / "run-report.example.json").exists()
    assert "outputs/SKILL.generated.md" in (task_dir / "task.md").read_text(encoding="utf-8")


def test_generate_skill_rewrite_reads_generated_skill_from_workspace_outputs(monkeypatch, tmp_path: Path) -> None:
    package_dir = tmp_path / "package"
    workspace_dir = tmp_path / "workspace"
    cycle_dir = workspace_dir / "cycles" / "kimi-cycle-test"
    (package_dir / "metadata").mkdir(parents=True)
    (package_dir / "evals").mkdir(parents=True)
    (package_dir / "references").mkdir(parents=True)

    (package_dir / "metadata" / "package.json").write_text(
        json.dumps(
            {
                "package_name": "golden-circle",
                "skill_name": "Golden Circle",
                "category": "thinking",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "evals" / "evals.json").write_text(
        json.dumps({"skill_name": "Golden Circle", "evals": [{"id": 101}]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (package_dir / "metadata" / "source-map.json").write_text(
        json.dumps({"package_name": "golden-circle", "source_mode": "demo-only", "demo_sources": [], "notes": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (package_dir / "SKILL.md").write_text("---\nname: old\ndescription: old\n---\n\n# Old\n", encoding="utf-8")
    (package_dir / "references" / "examples.md").write_text("# Examples\n\n- example", encoding="utf-8")

    def fake_workspace_task(task_prompt: str, task_dir: str | Path, **_: object) -> dict[str, object]:
        output_dir = Path(task_dir) / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        generated_path = output_dir / "SKILL.generated.md"
        generated_path.write_text("---\nname: new-skill\ndescription: Use when better.\n---\n\n# New Skill\n", encoding="utf-8")
        (output_dir / "run-report.json").write_text(
            json.dumps({"task": "skill-rewrite", "status": "completed", "files_written": ["outputs/SKILL.generated.md"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        return {
            "assistant_text": "done",
            "resolved_outputs": {
                "outputs/SKILL.generated.md": str(generated_path),
                "outputs/run-report.json": str(output_dir / "run-report.json"),
            },
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr("toolchain.kimi_cycle.skill_rewrite.run_kimi_workspace_task", fake_workspace_task)
    monkeypatch.setattr(
        "toolchain.kimi_cycle.skill_rewrite.validate_rewritten_skill",
        lambda package_dir, rewritten_skill: {
            "valid": True,
            "package_validator": {"summary": {"errors": 0, "warnings": 0}},
            "protocol_validator": {"summary": {"errors": 0, "warnings": 0}},
        },
    )

    result = generate_skill_rewrite(package_dir, workspace_dir, cycle_dir)

    assert result["valid"] is True
    assert Path(result["generated_skill_path"]).read_text(encoding="utf-8").startswith("---")
    assert "workspace\\outputs\\SKILL.generated.md" in result["generated_skill_path"] or "workspace/outputs/SKILL.generated.md" in result["generated_skill_path"]
