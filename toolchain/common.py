from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any, *, compact: bool = False) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
    target.write_text(payload, encoding="utf-8")


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def parse_eval_ids(value: str | None) -> list[int] | None:
    if not value:
        return None
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def filter_evals(
    evals: list[dict[str, Any]],
    *,
    eval_ids: list[int] | None = None,
    max_evals: int | None = None,
) -> list[dict[str, Any]]:
    filtered = list(evals)
    if eval_ids:
        selected = {int(item) for item in eval_ids}
        filtered = [item for item in filtered if int(item["id"]) in selected]
    if max_evals is not None:
        filtered = filtered[: max(0, int(max_evals))]
    return filtered


def run_number_from_dir(run_dir: str | Path) -> int:
    name = Path(run_dir).name
    try:
        return int(name.split("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def load_iteration_config(iteration_dir: str | Path) -> dict[str, Any]:
    path = Path(iteration_dir) / "iteration_config.json"
    if not path.exists():
        return {}
    data = load_json(path)
    return data if isinstance(data, dict) else {}


def active_run_limit(iteration_dir: str | Path) -> int | None:
    config = load_iteration_config(iteration_dir)
    raw_limit = config.get("runs_per_configuration")
    if raw_limit is None:
        return None
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None


def is_active_run_dir(run_dir: str | Path, iteration_dir: str | Path | None = None) -> bool:
    run_path = Path(run_dir)
    resolved_iteration_dir = Path(iteration_dir) if iteration_dir is not None else run_path.parent.parent.parent
    limit = active_run_limit(resolved_iteration_dir)
    if limit is None:
        return True
    run_number = run_number_from_dir(run_path)
    return 0 < run_number <= limit


def slugify(text: str, max_length: int = 48, *, allow_unicode: bool = False) -> str:
    pattern = r"[^a-z0-9\u4e00-\u9fff]+" if allow_unicode else r"[^a-z0-9]+"
    cleaned = text.strip().lower()
    cleaned = re.sub(pattern, "-", cleaned)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    cleaned = cleaned[:max_length].rstrip("-")
    return cleaned or "eval"


def extract_json_object(text: str, *, error_message: str = "Text did not contain a JSON object.") -> dict[str, Any]:
    payload = text.strip()
    fenced = re.search(r"```json\s*(\{.*\})\s*```", payload, re.DOTALL | re.IGNORECASE)
    candidate = fenced.group(1) if fenced else payload
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(error_message)
    parsed = json.loads(candidate[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError(error_message)
    return parsed


def compact_text(text: str, max_chars: int, *, tail_min_chars: int = 300) -> str:
    normalized = text.strip()
    if max_chars <= 0:
        return ""
    if len(normalized) <= max_chars:
        return normalized
    marker = "\n\n...[truncated]...\n\n"
    if max_chars <= len(marker) + 2:
        return normalized[:max_chars].strip()

    available = max_chars - len(marker)
    tail_chars = max(1, min(max(tail_min_chars, available // 3), available // 2))
    head_chars = max(1, available - tail_chars)
    head = normalized[:head_chars].strip()
    tail = normalized[-tail_chars:].strip()
    return f"{head}{marker}{tail}"[:max_chars]
