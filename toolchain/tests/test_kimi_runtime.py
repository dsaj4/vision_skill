from __future__ import annotations

import json
from pathlib import Path

from toolchain.kimi_runtime import (
    build_kimi_args,
    content_to_text,
    extract_assistant_message,
    extract_resume_session_id,
    parse_jsonl,
)


def test_parse_jsonl_returns_messages_and_warnings() -> None:
    messages, warnings = parse_jsonl(
        "\n".join(
            [
                json.dumps({"role": "assistant", "content": "ok"}),
                "not-json",
                json.dumps(["not", "message"]),
            ]
        )
    )

    assert messages == [{"role": "assistant", "content": "ok"}]
    assert warnings == ["not-json", '["not", "message"]']


def test_content_to_text_normalizes_kimi_content_shapes() -> None:
    assert content_to_text(" hello ") == "hello"
    assert content_to_text([{"text": "first"}, {"content": "second"}, "third"]) == "first\nsecond\nthird"
    assert content_to_text(None) == ""


def test_extract_assistant_message_uses_last_assistant_text() -> None:
    messages = [
        {"role": "assistant", "content": "draft"},
        {"role": "tool", "content": "tool output"},
        {"role": "assistant", "content": [{"text": "final"}]},
    ]

    assert extract_assistant_message(messages, fallback_stdout="fallback") == "final"
    assert extract_assistant_message([], fallback_stdout="fallback") == "fallback"


def test_extract_resume_session_id_reads_latest_resume_hint() -> None:
    stderr = "older kimi -r session-1\nTo resume this session: kimi -r session-2\n"

    assert extract_resume_session_id(stderr) == "session-2"


def test_build_kimi_args_is_canonical(monkeypatch, tmp_path: Path) -> None:
    kimi_exe = tmp_path / "kimi.exe"
    kimi_exe.write_text("", encoding="utf-8")
    monkeypatch.setenv("KIMI_CLI_EXECUTABLE", str(kimi_exe))

    args = build_kimi_args(
        work_dir=tmp_path / "workspace",
        prompt="do work",
        model="kimi-for-coding",
        output_format="stream-json",
        final_message_only=True,
        add_dir=tmp_path / "package",
        skills_dir=tmp_path / "skills",
        session_id="session-123",
    )

    assert args[:3] == [str(kimi_exe), "--print", "--output-format=stream-json"]
    assert "--final-message-only" in args
    assert args[args.index("--work-dir") + 1] == str(tmp_path / "workspace")
    assert args[args.index("--add-dir") + 1] == str(tmp_path / "package")
    assert args[args.index("--skills-dir") + 1] == str(tmp_path / "skills")
    assert args[args.index("--session") + 1] == "session-123"
    assert args[args.index("--model") + 1] == "kimi-for-coding"
    assert args[-2:] == ["--prompt", "do work"]
