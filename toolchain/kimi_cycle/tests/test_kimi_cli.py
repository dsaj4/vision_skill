from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.kimi_cycle.kimi_cli import extract_markdown_document


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
