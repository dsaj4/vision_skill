from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from toolchain.eval_factory.sync import resolve_package_evals


def _slugify(text: str, max_length: int = 48) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:max_length].rstrip("-") or "eval"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_history(workspace_dir: Path, package_name: str, skill_name: str) -> Path:
    history_path = workspace_dir / "history.json"
    if not history_path.exists():
        _write_json(
            history_path,
            {
                "started_at": "",
                "package_name": package_name,
                "skill_name": skill_name,
                "current_best": "candidate-seed",
                "iterations": [],
            },
        )
    return history_path


def _filter_evals(
    evals: list[dict[str, Any]],
    *,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
) -> list[dict[str, Any]]:
    filtered = evals
    if eval_ids:
        selected = {int(item) for item in eval_ids}
        filtered = [item for item in filtered if int(item["id"]) in selected]
    if max_evals is not None:
        filtered = filtered[:max(0, int(max_evals))]
    return filtered


def prepare_iteration(
    package_path: str | Path,
    workspace_path: str | Path,
    iteration_number: int,
    runs_per_configuration: int = 1,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
) -> dict[str, Any]:
    package_dir = Path(package_path)
    workspace_dir = Path(workspace_path)
    eval_resolution = resolve_package_evals(package_dir)
    evals_data = eval_resolution["data"]
    package_meta = _load_json(package_dir / "metadata" / "package.json")

    package_name = package_meta["package_name"]
    skill_name = package_meta["skill_name"]
    workspace_dir.mkdir(parents=True, exist_ok=True)
    history_path = _ensure_history(workspace_dir, package_name, skill_name)

    iteration_dir = workspace_dir / f"iteration-{iteration_number}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    selected_evals = _filter_evals(
        list(evals_data["evals"]),
        eval_ids=eval_ids,
        max_evals=max_evals,
    )

    created_eval_dirs: list[str] = []
    for eval_item in selected_evals:
        eval_name = _slugify(eval_item["prompt"])
        eval_dir = iteration_dir / f"eval-{eval_item['id']}-{eval_name}"
        eval_dir.mkdir(parents=True, exist_ok=True)

        _write_json(
            eval_dir / "eval_metadata.json",
            {
                "eval_id": eval_item["id"],
                "eval_name": eval_name,
                "prompt": eval_item["prompt"],
                "expected_output": eval_item["expected_output"],
                "files": eval_item.get("files", []),
                "assertions": eval_item.get("expectations", []),
                "host_eval": eval_item.get("host_eval", {}),
            },
        )

        for configuration in ("with_skill", "without_skill"):
            for run_number in range(1, runs_per_configuration + 1):
                run_dir = eval_dir / configuration / f"run-{run_number}"
                (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
                (run_dir / "README.md").write_text(
                    "\n".join(
                        [
                            f"# {configuration} / run-{run_number}",
                            "",
                            f"Prompt: {eval_item['prompt']}",
                            "",
                            "Expected artifacts for this run:",
                            "- outputs/",
                            "- grading.json",
                            "- timing.json",
                        ]
                    ),
                    encoding="utf-8",
                )

        created_eval_dirs.append(str(eval_dir))

    history = _load_json(history_path)
    version_name = f"iteration-{iteration_number}"
    existing_versions = {item.get("version") for item in history.get("iterations", [])}
    if version_name not in existing_versions:
        history.setdefault("iterations", []).append(
            {
                "version": version_name,
                "parent": history.get("current_best"),
                "stage": "prepared",
                "grading_result": "not-run",
                "is_current_best": False,
            }
        )
        _write_json(history_path, history)

    return {
        "created": True,
        "iteration_dir": str(iteration_dir),
        "eval_directories": created_eval_dirs,
        "runs_per_configuration": runs_per_configuration,
        "eval_source_mode": eval_resolution["source_mode"],
        "selected_eval_ids": [int(item["id"]) for item in selected_evals],
        "selected_eval_count": len(selected_evals),
    }
