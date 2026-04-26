# Agent Hosts

This module contains Kimi Code host validation.

Purpose:

- verify that a skill is discoverable inside Kimi Code
- verify that multi-turn protocol behavior survives the real host layer
- extract richer rule-based host signals without sending raw transcripts to a model

Current backend:

- `KimiCodeHost`
  - creates a workspace-local `.kimi/skills/<package>/SKILL.md` proxy
  - runs Kimi Code through `kimi --print --output-format=stream-json`
  - uses `--work-dir`, `--add-dir`, `--skills-dir`, and `--session` so the host can read the canonical package while keeping eval artifacts isolated
  - forces UTF-8 Python subprocess output on Windows to avoid GBK failures when a skill contains Chinese text
  - runs `kimi` directly instead of through a PowerShell wrapper so normal stderr lines like `To resume this session` do not become false failures

Model selection:

- default: let Kimi CLI use the model from its own login/config state
- optional override: set `KIMI_CLI_MODEL`

Current entry point:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 4 --max-evals 4
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

Extraction chain:

```text
raw Kimi host transcript
  -> simple cleaning
  -> normalized events
  -> signal report
  -> protocol classification
  -> host benchmark
```

Prompt control rules:

- do not send raw `host-transcript.json` to a model
- do not send the full `SKILL.md` to a host analysis prompt
- use only compact packets derived from `host-signal-report.json`
- each evidence snippet is capped at `240` characters
- each host analysis packet is capped at `1800` characters
