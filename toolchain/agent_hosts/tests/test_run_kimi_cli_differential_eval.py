from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.agent_hosts.run_kimi_cli_differential_eval import (
    _parse_judge_decision,
    _slugify,
    _trim_for_judge,
)


def test_parse_judge_decision_accepts_wrapped_json() -> None:
    text = 'Some preface {"winner":"A","margin":0.72,"reason":"A is more direct."} trailing'
    result = _parse_judge_decision(text)

    assert result["winner"] == "a"
    assert result["margin"] == 0.72
    assert result["reason"] == "A is more direct."


def test_parse_judge_decision_accepts_fenced_json() -> None:
    text = '```json\n{"winner":"B","margin":0.4,"reason":"B is clearer."}\n```'
    result = _parse_judge_decision(text)

    assert result["winner"] == "b"
    assert result["margin"] == 0.4
    assert result["reason"] == "B is clearer."


def test_parse_judge_decision_normalizes_invalid_values() -> None:
    text = '{"winner":"invalid","margin":9,"reason":"x"}'
    result = _parse_judge_decision(text)

    assert result["winner"] == "tie"
    assert result["margin"] == 1.0


def test_trim_for_judge_preserves_head_and_tail() -> None:
    original = "A" * 3000 + "MIDDLE" + "B" * 3000
    trimmed = _trim_for_judge(original, 1200)

    assert len(trimmed) < len(original)
    assert trimmed.startswith("A" * 600)
    assert trimmed.endswith("B" * 400)
    assert "...[truncated]..." in trimmed


def test_slugify_keeps_chinese_and_ascii() -> None:
    assert _slugify("MECE 原则 / base prompt") == "mece-原则-base-prompt"
