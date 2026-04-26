from __future__ import annotations

from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.kimi_cycle.kimi_cli import extract_markdown_document, run_kimi_workspace_task
from toolchain.kimi_command import resolve_kimi_command


def test_extract_markdown_document_returns_full_multiline_body() -> None:
    raw = """```markdown
---
name: demo
description: Use when demo.
---

# Title

Line 1
Line 2
```"""
    extracted = extract_markdown_document(raw)
    assert extracted.startswith("---")
    assert "Line 1" in extracted
    assert "Line 2" in extracted


def test_extract_markdown_document_keeps_unfenced_document_with_inner_code_block() -> None:
    raw = """---
name: demo
description: Use when demo.
---

# Title

```text
inner block
```
"""
    extracted = extract_markdown_document(raw)
    assert extracted.startswith("---")
    assert "inner block" in extracted


def test_run_kimi_workspace_task_requires_expected_output_files(tmp_path: Path) -> None:
    recorded_args: list[list[str]] = []
    task_dir = tmp_path / "workspace-task"

    def fake_runner(args: list[str], cwd: Path, timeout_seconds: int | None) -> dict[str, str | int]:
        recorded_args.append(args)
        output_path = cwd / "outputs" / "result.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('{"ok": true}', encoding="utf-8")
        stdout = json.dumps({"role": "assistant", "content": "Finished writing outputs."}, ensure_ascii=False)
        return {"returncode": 0, "stdout": stdout + "\n", "stderr": ""}

    result = run_kimi_workspace_task(
        "Read task.md and write outputs/result.json.",
        task_dir,
        required_outputs=["outputs/result.json"],
        model="kimi-for-coding",
        command_runner=fake_runner,
    )

    assert result["assistant_text"] == "Finished writing outputs."
    assert Path(result["resolved_outputs"]["outputs/result.json"]).read_text(encoding="utf-8") == '{"ok": true}'
    assert Path(recorded_args[0][0]).name.lower() in {"kimi", "kimi.exe", "kimi.cmd", "kimi-cli.exe"}
    assert recorded_args[0][1:3] == ["--print", "--output-format=stream-json"]
    assert "--work-dir" in recorded_args[0]
    assert "--model" in recorded_args[0]
    assert recorded_args[0][-2] == "--prompt"


def test_resolve_kimi_command_falls_back_to_local_bin(monkeypatch, tmp_path: Path) -> None:
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    kimi_exe = local_bin / "kimi.exe"
    kimi_exe.write_text("", encoding="utf-8")

    monkeypatch.delenv("KIMI_CLI_EXECUTABLE", raising=False)
    monkeypatch.setattr("toolchain.kimi_runtime.shutil.which", lambda _: None)
    monkeypatch.setattr("toolchain.kimi_runtime.Path.home", lambda: tmp_path)

    assert resolve_kimi_command() == str(kimi_exe)
