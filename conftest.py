from __future__ import annotations

from pathlib import Path
import re
import shutil
from uuid import uuid4

import pytest


def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "tmp"


@pytest.fixture
def tmp_path(request) -> Path:
    repo_root = Path(__file__).resolve().parent
    base_dir = repo_root / "toolchain" / ".tmp-fixtures"
    case_dir = base_dir / f"{_slugify(request.node.name)}-{uuid4().hex[:8]}"
    if case_dir.exists():
        shutil.rmtree(case_dir, ignore_errors=True)
    case_dir.mkdir(parents=True, exist_ok=True)
    yield case_dir
    shutil.rmtree(case_dir, ignore_errors=True)
