from __future__ import annotations

from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.kimi_cycle.eval_generation import normalize_generated_eval_set, prepare_eval_generation_workspace


def test_normalize_generated_eval_set_fills_root_and_ids() -> None:
    raw = """
    {
      "evals": [
        {
          "prompt": "Analyze this case directly.",
          "expected_output": "Direct result.",
          "files": [],
          "expectations": [{"text": "Should mention result", "keywords": ["result"]}]
        },
        {
          "id": 101,
          "prompt": "Ask only for missing information.",
          "expected_output": "Missing info follow-up.",
          "files": [],
          "expectations": [{"id": "missing", "type": "contains_none", "text": "No full answer", "keywords": ["full answer"]}],
          "host_eval": {"turn_script": ["first", {"text": "continue"}], "expected_protocol_path": "staged -> continue-loop"}
        }
      ]
    }
    """
    package_meta = {"package_name": "golden-circle", "skill_name": "Golden Circle"}
    current_root = {"skill_name": "Golden Circle", "package_name": "golden-circle", "evals": [{"id": 101}]}

    normalized = normalize_generated_eval_set(raw, package_meta, current_root)

    assert normalized["package_name"] == "golden-circle"
    assert normalized["skill_name"] == "Golden Circle"
    assert len(normalized["evals"]) == 2
    assert normalized["evals"][0]["id"] == 101
    assert normalized["evals"][1]["id"] == 102
    assert normalized["evals"][0]["host_eval"]["enabled"] is True
    assert normalized["evals"][0]["host_eval"]["turn_script"][1] == {"text": "continue"}
    assert normalized["evals"][1]["expectations"][0]["id"].startswith("eval-102-exp-")


def test_prepare_eval_generation_workspace_writes_manifest_inputs_and_examples(tmp_path: Path) -> None:
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
        json.dumps(
            {
                "skill_name": "Golden Circle",
                "package_name": "golden-circle",
                "evals": [{"id": 101, "prompt": "demo", "expected_output": "demo", "files": [], "expectations": []}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (package_dir / "SKILL.md").write_text("---\nname: golden-circle\ndescription: Use when needed.\n---\n\n# Golden Circle\n", encoding="utf-8")
    (package_dir / "references" / "examples.md").write_text("# Examples\n\n- direct result example", encoding="utf-8")

    result = prepare_eval_generation_workspace(package_dir, workspace_dir, cycle_dir)

    task_dir = Path(result["task_dir"])
    assert (task_dir / "task.md").exists()
    assert (task_dir / "workspace-manifest.json").exists()
    assert (task_dir / "inputs" / "package-packet.json").exists()
    assert (task_dir / "inputs" / "recent-context.json").exists()
    assert (task_dir / "inputs" / "current-evals.json").exists()
    assert (task_dir / "inputs" / "current-skill.md").exists()
    assert (task_dir / "inputs" / "examples.md").exists()
    assert (task_dir / "contracts" / "output-contract.md").exists()
    assert (task_dir / "examples" / "eval-draft.example.json").exists()
    assert (task_dir / "examples" / "run-report.example.json").exists()
    assert "outputs/eval-draft.json" in (task_dir / "task.md").read_text(encoding="utf-8")
