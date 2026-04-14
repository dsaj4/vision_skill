from __future__ import annotations

import html
import re
from typing import Any


MAX_EVIDENCE_SNIPPET_CHARS = 240
MAX_EVIDENCE_SNIPPETS_PER_EVAL = 6
MAX_HOST_PACKET_CHARS = 1800
MAX_SKILL_PROTOCOL_SUMMARY_CHARS = 800
MAX_TOTAL_HOST_ANALYSIS_CHARS = 4000

PROMPT_BUDGET = {
    "max_evidence_snippet_chars": MAX_EVIDENCE_SNIPPET_CHARS,
    "max_evidence_snippets_per_eval": MAX_EVIDENCE_SNIPPETS_PER_EVAL,
    "max_host_packet_chars": MAX_HOST_PACKET_CHARS,
    "max_skill_protocol_summary_chars": MAX_SKILL_PROTOCOL_SUMMARY_CHARS,
    "max_total_host_analysis_chars": MAX_TOTAL_HOST_ANALYSIS_CHARS,
}

ANSI_ESCAPE_RE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MULTISPACE_RE = re.compile(r"[ \t]+")
MULTIBLANK_RE = re.compile(r"\n{3,}")
TIMESTAMP_WARN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", re.MULTILINE)

HOST_NOISE_PATTERNS = {
    "plugin_interference": [
        "codex_core::plugins::manifest",
        "interface.defaultprompt",
        ".codex-plugin/plugin.json",
        "plugins\\plugins\\",
    ],
    "network_interference": [
        "cloudflare",
        "__cf_chl",
        "enable javascript and cookies to continue",
        "<html",
        "<script",
        "/cdn-cgi/challenge-platform",
    ],
    "noise_warning": [
        "propertysetternotsupportedinconstrainedlanguage",
        "constrainedlanguage",
        "[console]::outputencoding",
        "warning",
        "warn ",
    ],
}

SKILL_METADATA_HINTS = [
    "metadata/package.json",
    "evals/evals.json",
    "metadata\\package.json",
    "evals\\evals.json",
]


def normalize_path_text(value: str) -> str:
    return value.replace("\\", "/").lower().strip()


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _strip_html(text: str) -> str:
    if "<" not in text or ">" not in text:
        return text
    without_tags = HTML_TAG_RE.sub(" ", text)
    return html.unescape(without_tags)


def _collapse_whitespace(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = MULTISPACE_RE.sub(" ", normalized)
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    normalized = MULTIBLANK_RE.sub("\n\n", normalized)
    return normalized.strip()


def _keyword_windows(text: str, keywords: list[str], window: int = 72) -> list[str]:
    lowered = text.lower()
    windows: list[str] = []
    for keyword in keywords:
        index = lowered.find(keyword.lower())
        if index == -1:
            continue
        start = max(index - window, 0)
        end = min(index + len(keyword) + window, len(text))
        windows.append(text[start:end].strip())
    return _dedupe_preserve_order(windows)


def _compress_text(text: str, limit: int, keywords: list[str]) -> str:
    if len(text) <= limit:
        return text

    segments: list[str] = []
    start_segment = text[: max(60, limit // 4)].strip()
    if start_segment:
        segments.append(start_segment)

    for window in _keyword_windows(text, keywords):
        if window and window not in segments:
            segments.append(window)
        if sum(len(item) for item in segments) >= limit:
            break

    end_segment = text[-max(60, limit // 4) :].strip()
    if end_segment and end_segment not in segments:
        segments.append(end_segment)

    compact = " ... ".join(item for item in segments if item)
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 16)].rstrip() + " ...[truncated]"


def clean_text_fragment(text: str, *, limit: int = MAX_EVIDENCE_SNIPPET_CHARS, keywords: list[str] | None = None) -> str:
    normalized = ANSI_ESCAPE_RE.sub("", text or "")
    normalized = _strip_html(normalized)
    normalized = _collapse_whitespace(normalized)
    if not normalized:
        return ""
    return _compress_text(normalized, limit, keywords or [])


def _noise_type(text: str) -> str | None:
    lowered = normalize_path_text(text)
    for event_type, patterns in HOST_NOISE_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            return event_type
    if TIMESTAMP_WARN_RE.search(text) and "warn" in lowered:
        return "noise_warning"
    return None


def _normalize_event(
    *,
    turn_index: int,
    event_type: str,
    source: str,
    raw_ref: str,
    evidence_text: str,
    timestamp_hint: str = "",
    is_noise: bool = False,
    noise_kind: str = "",
) -> dict[str, Any]:
    return {
        "turn_index": int(turn_index),
        "event_type": event_type,
        "source": source,
        "timestamp_hint": timestamp_hint,
        "raw_ref": raw_ref,
        "evidence_text": evidence_text,
        "is_noise": bool(is_noise),
        "noise_kind": noise_kind,
    }


def _command_event_type(command: str, output: str, transcript: dict[str, Any]) -> tuple[str, bool, str]:
    combined = normalize_path_text(f"{command}\n{output}")
    proxy_path = normalize_path_text(str(transcript.get("proxy_skill_path", "")))
    canonical_path = normalize_path_text(str(transcript.get("canonical_skill_path", "")))
    package_dir = normalize_path_text(str(transcript.get("package_dir", "")))

    if proxy_path and proxy_path in combined:
        return "skill_proxy_read", False, ""
    if canonical_path and canonical_path in combined:
        return "skill_canonical_read", False, ""
    if package_dir and any(hint in combined for hint in SKILL_METADATA_HINTS):
        return "skill_meta_read", False, ""

    noise_kind = _noise_type(f"{command}\n{output}")
    if noise_kind:
        return noise_kind, True, noise_kind
    return "command_completed", False, ""


def normalize_host_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    seen_noise: set[tuple[str, str]] = set()

    for turn_index, turn in enumerate(transcript.get("turns", []), start=1):
        user_text = clean_text_fragment(str(turn.get("user_text", "")), limit=MAX_EVIDENCE_SNIPPET_CHARS)
        if user_text:
            events.append(
                _normalize_event(
                    turn_index=turn_index,
                    event_type="turn_started",
                    source="transcript.turn",
                    raw_ref=f"turn:{turn_index}:user_text",
                    evidence_text=user_text,
                )
            )

        raw_events = list(turn.get("events", []))
        final_assistant_text = clean_text_fragment(str(turn.get("assistant_text", "")), limit=MAX_EVIDENCE_SNIPPET_CHARS)

        for event_index, raw_event in enumerate(raw_events):
            event_type = str(raw_event.get("type", ""))
            raw_ref = f"turn:{turn_index}:event:{event_index}"
            item = raw_event.get("item", {})
            item_type = str(item.get("type", ""))

            if event_type == "item.started" and item_type == "command_execution":
                command_text = clean_text_fragment(str(item.get("command", "")), limit=MAX_EVIDENCE_SNIPPET_CHARS)
                if command_text:
                    events.append(
                        _normalize_event(
                            turn_index=turn_index,
                            event_type="command_started",
                            source="transcript.events",
                            raw_ref=raw_ref,
                            evidence_text=command_text,
                        )
                    )
                continue

            if event_type == "item.completed" and item_type == "command_execution":
                command = str(item.get("command", ""))
                output = str(item.get("aggregated_output", ""))
                normalized_type, is_noise, noise_kind = _command_event_type(command, output, transcript)
                keywords = [
                    str(transcript.get("proxy_skill_path", "")),
                    str(transcript.get("canonical_skill_path", "")),
                    "continue",
                    "revise",
                    "checkpoint",
                    "swot",
                    "strength",
                    "weakness",
                    "opportunities",
                    "threats",
                ]
                evidence_text = clean_text_fragment(
                    f"{command}\n{output}",
                    limit=MAX_EVIDENCE_SNIPPET_CHARS,
                    keywords=keywords,
                )
                dedupe_key = (normalized_type, evidence_text)
                if is_noise and dedupe_key in seen_noise:
                    continue
                if is_noise:
                    seen_noise.add(dedupe_key)
                if evidence_text:
                    events.append(
                        _normalize_event(
                            turn_index=turn_index,
                            event_type=normalized_type,
                            source="transcript.events",
                            raw_ref=raw_ref,
                            evidence_text=evidence_text,
                            is_noise=is_noise,
                            noise_kind=noise_kind,
                        )
                    )
                continue

            if event_type == "item.completed" and item_type == "agent_message":
                message_text = str(item.get("text", ""))
                cleaned = clean_text_fragment(message_text, limit=MAX_EVIDENCE_SNIPPET_CHARS)
                if not cleaned:
                    continue
                if cleaned == final_assistant_text:
                    continue
                is_noise = "skill" in cleaned.lower() or "read" in cleaned.lower() or "using-superpowers" in cleaned.lower()
                events.append(
                    _normalize_event(
                        turn_index=turn_index,
                        event_type="host_status_message" if is_noise else "agent_message",
                        source="transcript.events",
                        raw_ref=raw_ref,
                        evidence_text=cleaned,
                        is_noise=is_noise,
                        noise_kind="behavior_noise" if is_noise else "",
                    )
                )

        for warning_index, warning in enumerate(_dedupe_preserve_order(list(turn.get("warnings", [])))):
            cleaned = clean_text_fragment(str(warning), limit=MAX_EVIDENCE_SNIPPET_CHARS)
            if not cleaned:
                continue
            noise_kind = _noise_type(cleaned) or "noise_warning"
            dedupe_key = (noise_kind, cleaned)
            if dedupe_key in seen_noise:
                continue
            seen_noise.add(dedupe_key)
            events.append(
                _normalize_event(
                    turn_index=turn_index,
                    event_type=noise_kind,
                    source="transcript.warnings",
                    raw_ref=f"turn:{turn_index}:warning:{warning_index}",
                    evidence_text=cleaned,
                    is_noise=True,
                    noise_kind=noise_kind,
                )
            )

        stderr_text = str(turn.get("stderr", "") or "")
        if stderr_text.strip():
            for stderr_index, line in enumerate(_dedupe_preserve_order(stderr_text.splitlines())):
                cleaned = clean_text_fragment(line, limit=MAX_EVIDENCE_SNIPPET_CHARS)
                if not cleaned:
                    continue
                noise_kind = _noise_type(cleaned) or "noise_warning"
                dedupe_key = (noise_kind, cleaned)
                if dedupe_key in seen_noise:
                    continue
                seen_noise.add(dedupe_key)
                events.append(
                    _normalize_event(
                        turn_index=turn_index,
                        event_type=noise_kind,
                        source="transcript.stderr",
                        raw_ref=f"turn:{turn_index}:stderr:{stderr_index}",
                        evidence_text=cleaned,
                        is_noise=True,
                        noise_kind=noise_kind,
                    )
                )

        if final_assistant_text:
            events.append(
                _normalize_event(
                    turn_index=turn_index,
                    event_type="agent_message",
                    source="transcript.turn",
                    raw_ref=f"turn:{turn_index}:assistant_text",
                    evidence_text=final_assistant_text,
                )
            )

    return {
        "metadata": {
            "thread_id": transcript.get("thread_id"),
            "package_name": transcript.get("package_name", ""),
            "package_dir": transcript.get("package_dir", ""),
            "proxy_skill_path": transcript.get("proxy_skill_path", ""),
            "canonical_skill_path": transcript.get("canonical_skill_path", ""),
            "turn_count": len(transcript.get("turns", [])),
            "prompt_budget": PROMPT_BUDGET,
        },
        "events": events,
    }


__all__ = [
    "MAX_EVIDENCE_SNIPPET_CHARS",
    "MAX_EVIDENCE_SNIPPETS_PER_EVAL",
    "MAX_HOST_PACKET_CHARS",
    "MAX_SKILL_PROTOCOL_SUMMARY_CHARS",
    "MAX_TOTAL_HOST_ANALYSIS_CHARS",
    "PROMPT_BUDGET",
    "clean_text_fragment",
    "normalize_host_transcript",
    "normalize_path_text",
]
