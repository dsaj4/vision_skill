from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from toolchain.agent_hosts.event_normalizer import clean_text_fragment, normalize_host_transcript


def test_clean_text_fragment_strips_ansi_html_and_compacts() -> None:
    raw = "\x1b[31m<html><body>Enable JavaScript and cookies to continue</body></html>\x1b[0m"
    cleaned = clean_text_fragment(raw, limit=80)
    assert "\x1b" not in cleaned
    assert "<html>" not in cleaned
    assert "Enable JavaScript" in cleaned


def test_normalize_host_transcript_captures_skill_reads_and_noise() -> None:
    transcript = {
        "thread_id": "thread-1",
        "package_name": "swot-analysis",
        "package_dir": "E:/repo/packages/swot-analysis",
        "proxy_skill_path": "E:/repo/session/.kimi/skills/swot-analysis/SKILL.md",
        "canonical_skill_path": "E:/repo/packages/swot-analysis/SKILL.md",
        "turns": [
            {
                "turn_index": 1,
                "user_text": "Help me with SWOT.",
                "assistant_text": "Before I can continue, I need more context.",
                "events": [
                    {
                        "type": "item.started",
                        "item": {"type": "command_execution", "command": "Get-Content proxy"},
                    },
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "Get-Content 'E:/repo/session/.kimi/skills/swot-analysis/SKILL.md'",
                            "aggregated_output": "proxy skill text",
                        },
                    },
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "Get-Content 'E:/repo/packages/swot-analysis/SKILL.md'",
                            "aggregated_output": "canonical skill text",
                        },
                    },
                ],
                "warnings": [
                    "2026-04-14T12:08:15Z WARN codex_core::plugins::manifest: ignoring interface.defaultPrompt",
                    "2026-04-14T12:08:15Z WARN codex_core::plugins::manifest: ignoring interface.defaultPrompt",
                ],
                "stderr": "PropertySetterNotSupportedInConstrainedLanguage",
            }
        ],
    }

    normalized = normalize_host_transcript(transcript)
    event_types = [item["event_type"] for item in normalized["events"]]

    assert "turn_started" in event_types
    assert "skill_proxy_read" in event_types
    assert "skill_canonical_read" in event_types
    assert "plugin_interference" in event_types
    assert "noise_warning" in event_types
    assert event_types.count("plugin_interference") == 1
