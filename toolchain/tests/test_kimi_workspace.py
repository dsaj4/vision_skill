from __future__ import annotations

import json
from pathlib import Path

from toolchain.kimi_workspace import (
    load_workspace_json,
    read_workspace_text,
    run_kimi_workspace_task,
    write_workspace_task,
)


def test_workspace_task_writes_manifest_inputs_and_reads_outputs(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    manifest = write_workspace_task(
        task_dir,
        task_markdown="# Task\nWrite the answer.",
        required_outputs=["outputs/answer.md", "outputs/meta.json"],
        inputs={"inputs/request.json": {"prompt": "hello"}},
        contract_markdown="# Contract\nWrite files.",
        metadata={"task_type": "unit-test"},
    )

    assert manifest["result_source_of_truth"] == "workspace-output-files"
    assert (task_dir / "task.md").exists()
    assert json.loads((task_dir / "inputs" / "request.json").read_text(encoding="utf-8")) == {"prompt": "hello"}
    assert "outputs/answer.md" in json.loads((task_dir / "workspace-manifest.json").read_text(encoding="utf-8"))["required_outputs"]


def test_run_workspace_task_requires_files_and_ignores_terminal_answer(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    write_workspace_task(
        task_dir,
        task_markdown="# Task",
        required_outputs=["outputs/answer.md", "outputs/meta.json"],
    )

    def fake_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, str | int]:
        (cwd / "outputs").mkdir(parents=True, exist_ok=True)
        (cwd / "outputs" / "answer.md").write_text("file answer", encoding="utf-8")
        (cwd / "outputs" / "meta.json").write_text('{"ok": true}', encoding="utf-8")
        stdout = json.dumps({"role": "assistant", "content": "terminal log only"}, ensure_ascii=False)
        return {"returncode": 0, "stdout": stdout + "\n", "stderr": ""}

    result = run_kimi_workspace_task(
        task_dir,
        required_outputs=["outputs/answer.md", "outputs/meta.json"],
        command_runner=fake_runner,
    )

    assert result["assistant_text"] == "terminal log only"
    assert read_workspace_text(result, "outputs/answer.md") == "file answer"
    assert load_workspace_json(result, "outputs/meta.json") == {"ok": True}


def test_workspace_task_rejects_escaping_paths(tmp_path: Path) -> None:
    try:
        write_workspace_task(
            tmp_path / "task",
            task_markdown="# Task",
            required_outputs=["../escape.md"],
        )
    except ValueError as exc:
        assert "stay inside the task dir" in str(exc)
    else:
        raise AssertionError("Expected escaping output path to be rejected.")
