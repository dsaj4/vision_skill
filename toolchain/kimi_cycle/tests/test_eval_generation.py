from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.kimi_cycle.eval_generation import normalize_generated_eval_set


def test_normalize_generated_eval_set_fills_root_and_ids() -> None:
    raw = """
    {
      "evals": [
        {
          "prompt": "Analyze this case directly.",
          "expected_output": "Direct result.",
          "files": [],
          "expectations": [{"text": "Should mention result", "keywords": ["result"]}]
        },
        {
          "id": 101,
          "prompt": "Ask only for missing information.",
          "expected_output": "Missing info follow-up.",
          "files": [],
          "expectations": [{"id": "missing", "type": "contains_none", "text": "No full answer", "keywords": ["full answer"]}],
          "host_eval": {"turn_script": ["first", {"text": "continue"}], "expected_protocol_path": "staged -> continue-loop"}
        }
      ]
    }
    """
    package_meta = {"package_name": "golden-circle", "skill_name": "Golden Circle"}
    current_root = {"skill_name": "Golden Circle", "package_name": "golden-circle", "evals": [{"id": 101}]}

    normalized = normalize_generated_eval_set(raw, package_meta, current_root)

    assert normalized["package_name"] == "golden-circle"
    assert normalized["skill_name"] == "Golden Circle"
    assert len(normalized["evals"]) == 2
    assert normalized["evals"][0]["id"] == 101
    assert normalized["evals"][1]["id"] == 102
    assert normalized["evals"][0]["host_eval"]["enabled"] is True
    assert normalized["evals"][0]["host_eval"]["turn_script"][1] == {"text": "continue"}
    assert normalized["evals"][1]["expectations"][0]["id"].startswith("eval-102-exp-")
