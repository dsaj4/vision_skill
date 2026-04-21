from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .context import write_json, write_text


def _write_file_map(task_dir: Path, files: dict[str, str]) -> list[str]:
    written: list[str] = []
    for relative_path, content in files.items():
        target = task_dir / relative_path
        write_text(target, content)
        written.append(relative_path)
    return written


def prepare_workspace_bundle(
    task_dir: str | Path,
    *,
    task_name: str,
    objective: str,
    input_files: dict[str, str],
    contract_files: dict[str, str],
    example_files: dict[str, str],
    required_outputs: list[str],
) -> dict[str, Any]:
    root = Path(task_dir)
    root.mkdir(parents=True, exist_ok=True)

    written_inputs = _write_file_map(root, input_files)
    written_contracts = _write_file_map(root, contract_files)
    written_examples = _write_file_map(root, example_files)

    manifest = {
        "task_name": task_name,
        "controller": "codex",
        "objective": objective,
        "read_order": [
            "task.md",
            "workspace-manifest.json",
            *written_inputs,
            *written_contracts,
            *written_examples,
        ],
        "required_outputs": required_outputs,
        "allowed_write_roots": ["outputs/"],
        "do_not_modify": ["inputs/", "contracts/", "examples/"],
        "completion_rule": "Write the required files first, then return a short completion note.",
    }
    write_json(root / "workspace-manifest.json", manifest)

    task_md = "\n".join(
        [
            f"# {task_name}",
            "",
            "## Objective",
            "",
            objective,
            "",
            "## Required Workflow",
            "",
            "1. Read `workspace-manifest.json`.",
            "2. Read the input, contract, and example files listed there.",
            "3. Use file tools and multi-step reasoning as needed.",
            "4. Write only the required output files under `outputs/`.",
            "5. Do not modify any file under `inputs/`, `contracts/`, or `examples/`.",
            "6. After writing files, return a short completion note instead of pasting the full content.",
            "",
            "## Required Outputs",
            "",
            *[f"- `{path}`" for path in required_outputs],
            "",
        ]
    ).strip() + "\n"
    write_text(root / "task.md", task_md)

    task_prompt = "\n".join(
        [
            "Read `task.md` and `workspace-manifest.json` in the current working directory.",
            "Follow the file contracts exactly.",
            "Write the required files under `outputs/` only.",
            "When you are done, return one short completion note.",
        ]
    )

    return {
        "task_dir": str(root),
        "task_prompt": task_prompt,
        "required_outputs": required_outputs,
        "manifest_path": str(root / "workspace-manifest.json"),
        "task_path": str(root / "task.md"),
    }


def to_pretty_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
