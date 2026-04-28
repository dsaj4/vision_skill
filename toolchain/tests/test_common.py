from __future__ import annotations

import pytest

from toolchain.common import (
    active_run_limit,
    compact_text,
    extract_json_object,
    is_active_run_dir,
    load_json,
    parse_eval_ids,
    run_number_from_dir,
    slugify,
    write_json,
    write_text,
)


def test_json_and_text_helpers_create_parent_directories(tmp_path):
    json_path = tmp_path / "nested" / "data.json"
    text_path = tmp_path / "nested" / "note.md"

    write_json(json_path, {"ok": True, "items": [1, 2]})
    write_text(text_path, "hello")

    assert load_json(json_path) == {"ok": True, "items": [1, 2]}
    assert text_path.read_text(encoding="utf-8") == "hello"


def test_parse_eval_ids_ignores_empty_items() -> None:
    assert parse_eval_ids("1, 2,,3") == [1, 2, 3]
    assert parse_eval_ids(None) is None
    assert parse_eval_ids("") is None


def test_slugify_supports_ascii_and_unicode_modes() -> None:
    assert slugify("Golden Circle / Demo!") == "golden-circle-demo"
    assert slugify("黄金圈 思维", allow_unicode=True) == "黄金圈-思维"


def test_extract_json_object_handles_fenced_and_wrapped_json() -> None:
    assert extract_json_object('prefix ```json\n{"winner":"A"}\n``` suffix') == {"winner": "A"}
    assert extract_json_object('noise {"ok": true, "score": 2} tail') == {"ok": True, "score": 2}


def test_extract_json_object_rejects_missing_json() -> None:
    with pytest.raises(ValueError):
        extract_json_object("no object here")


def test_compact_text_enforces_hard_character_budget() -> None:
    source = "A" * 200 + "\nimportant middle\n" + "B" * 200
    compacted = compact_text(source, 80, tail_min_chars=20)

    assert len(compacted) <= 80
    assert "[truncated]" in compacted
    assert compacted.endswith("B" * 20)


def test_iteration_config_limits_active_run_dirs(tmp_path) -> None:
    iteration_dir = tmp_path / "iteration-1"
    run_1 = iteration_dir / "eval-1-sample" / "with_skill" / "run-1"
    run_2 = iteration_dir / "eval-1-sample" / "with_skill" / "run-2"
    run_1.mkdir(parents=True)
    run_2.mkdir(parents=True)

    assert run_number_from_dir(run_2) == 2
    assert active_run_limit(iteration_dir) is None
    assert is_active_run_dir(run_2, iteration_dir) is True

    write_json(iteration_dir / "iteration_config.json", {"runs_per_configuration": 1})

    assert active_run_limit(iteration_dir) == 1
    assert is_active_run_dir(run_1, iteration_dir) is True
    assert is_active_run_dir(run_2, iteration_dir) is False
