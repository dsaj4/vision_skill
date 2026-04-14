# Agent Host Adapter Contract V0.1

## Purpose

This contract defines how a real host agent plugs into the Vision host-eval lane.

The current reference backend is `Codex`, but the contract is written so other source-reading hosts can join later without changing the rest of the evaluation pipeline.

## Lane Split

The repository now has two formal evaluation lanes:

- `API Eval Lane`
  - cheap screening
  - certified eval calibration
  - differential benchmark
  - Level 4-6 analysis on prompt-level execution
- `Host Agent Eval Lane`
  - real host trigger validation
  - multi-turn protocol validation
  - release-preflight evidence for host fidelity

The host lane adds evidence. It does not replace the API lane.

## Required Adapter Interface

An adapter must implement:

```python
prepare_session(package_dir, eval_case) -> session_handle
send_user_turn(session_handle, text) -> host_response
read_transcript(session_handle) -> transcript
detect_skill_trigger(transcript, package_name) -> trigger_report
close_session(session_handle) -> close_result
```

## Session Handle

`prepare_session(...)` should return a serializable `session_handle` with at least:

- `package_name`
- `package_dir`
- `session_dir`
- `thread_id`

It may include more host-specific state if needed.

## Transcript Contract

`host-transcript.json` should contain at least:

```json
{
  "thread_id": "thread-123",
  "package_name": "swot-analysis",
  "package_dir": "E:/Project/vision-lab/vision-skill/packages/swot-analysis",
  "proxy_skill_path": "E:/.../.codex/skills/swot-analysis/SKILL.md",
  "canonical_skill_path": "E:/.../packages/swot-analysis/SKILL.md",
  "turns": [
    {
      "turn_index": 1,
      "user_text": "user input",
      "assistant_text": "assistant reply",
      "events": [],
      "command_events": [],
      "warnings": [],
      "stderr": ""
    }
  ]
}
```

`events` and `command_events` may remain host-specific, but they must stay serializable and reviewable.

## Derived Host Artifacts

The host lane now derives three additional rule-based artifacts from `host-transcript.json`:

- `host-normalized-events.json`
- `host-signal-report.json`
- `host-protocol-report.json`

These are generated after simple cleaning. They are not raw host output.

### host-normalized-events.json

Each normalized event must contain at least:

```json
{
  "turn_index": 1,
  "event_type": "skill_canonical_read",
  "source": "transcript.events",
  "timestamp_hint": "",
  "raw_ref": "turn:1:event:3",
  "evidence_text": "Get-Content ...",
  "is_noise": false
}
```

Allowed event families currently include:

- `turn_started`
- `agent_message`
- `command_started`
- `command_completed`
- `skill_proxy_read`
- `skill_canonical_read`
- `skill_meta_read`
- `host_status_message`
- `noise_warning`
- `network_interference`
- `plugin_interference`
- `unknown_event`

### host-signal-report.json

This artifact must group extracted signals into:

- `trigger_signals`
- `routing_signals`
- `protocol_signals`
- `output_structure_signals`
- `host_interference_signals`

It may additionally include compact evidence snippets and a budget-checked analysis packet.

### host-protocol-report.json

This artifact must contain at least:

```json
{
  "observed_protocol_path": "missing-info -> ask-followup",
  "path_confidence": 0.8,
  "supporting_signals": ["missing_info_detected"],
  "blocking_signals": []
}
```

## Trigger Report Contract

`host-trigger-report.json` should contain at least:

```json
{
  "package_name": "swot-analysis",
  "triggered": true,
  "false_trigger": false,
  "expected_trigger": true,
  "expected_trigger_signals": [
    "proxy_skill_read",
    "canonical_skill_read"
  ],
  "trigger_turn_index": 1,
  "first_answer_turn_index": 1,
  "first_skill_read_turn_index": 1,
  "skill_read_before_first_answer": true,
  "observed_trigger_signals": {
    "proxy_skill_read": true,
    "canonical_skill_read": true,
    "skill_meta_read": false,
    "explicit_skill_use_announcement": false
  },
  "evidence": [
    {
      "type": "proxy_skill_read",
      "turn_index": 1,
      "raw_ref": "turn:1:event:2",
      "detail": "E:/.../.codex/skills/swot-analysis/SKILL.md"
    }
  ]
}
```

Required semantics:

- `triggered`
  - whether the host actually consumed the skill
- `false_trigger`
  - whether the host triggered when the eval expected no trigger
- `evidence`
  - concrete, reviewable support for the trigger judgment

Protocol reconstruction now belongs in `host-protocol-report.json`, not `host-trigger-report.json`.

## Prompt Budget Contract

Any future host-side model analysis must use compact packets only.

Hard rules:

- do not send raw `host-transcript.json`
- do not send full `stderr`
- do not send full `command_events`
- do not send the full `SKILL.md`

Current default budget:

- evidence snippet: `<= 240` characters
- snippets per eval: `<= 6`
- host analysis packet: `<= 1800` characters
- skill protocol summary: `<= 800` characters
- total host analysis payload: `<= 4000` characters

## Host Final Response Contract

`host-final-response.md` must contain the final host-visible assistant answer for the eval.

This file is intentionally normalized so the host lane can reuse the current grading logic.

## Eval Case Extension

`evals/evals.json` may now include an optional `host_eval` block:

```json
{
  "id": 102,
  "prompt": "...",
  "expected_output": "...",
  "files": [],
  "expectations": [],
  "host_eval": {
    "enabled": true,
    "turn_script": [
      {"text": "first user turn"},
      {"text": "second user turn"}
    ],
    "expected_trigger": true,
    "expected_trigger_signals": [
      "proxy_skill_read",
      "canonical_skill_read"
    ],
    "expected_protocol_path": "missing-info -> ask-followup"
  }
}
```

These fields are optional and must not break the API lane.

## Current Codex Backend

The current reference backend is `toolchain.agent_hosts.codex_host.CodexHost`.

Current strategy:

1. create a workspace-local proxy skill in `.codex/skills/<package>/SKILL.md`
2. keep the canonical package `SKILL.md` as the source of truth
3. run `codex exec` / `codex exec resume`
4. reconstruct trigger evidence from Codex event output

## Runner Entry Point

```bash
python -m toolchain.agent_hosts.run_host_eval --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 4 --max-evals 4
```

Current artifacts:

- `host-eval-<id>/host-session.json`
- `host-eval-<id>/host-transcript.json`
- `host-eval-<id>/host-normalized-events.json`
- `host-eval-<id>/host-signal-report.json`
- `host-eval-<id>/host-protocol-report.json`
- `host-eval-<id>/host-trigger-report.json`
- `host-eval-<id>/host-analysis-packet.json`
- `host-eval-<id>/host-final-response.md`
- `host-eval-<id>/host-grading.json`
- `host-benchmark.json`

## Current Limits

- v0.1 focuses on `trigger + multi-turn protocol`
- tool calling and long-lived external state are out of scope
- `Codex` is the only implemented backend
- host lane remains parallel to current `release-recommendation.json`
