# Agent Hosts

This module contains the real host-eval lane.

Purpose:

- verify that a skill is discoverable inside a real host
- verify that multi-turn protocol behavior survives the host layer
- keep host evidence separate from the API eval lane
- extract richer rule-based host signals without sending raw transcripts to a model

Current backends:

- `CodexHost`
  - creates a workspace-local `.codex/skills/<package>/SKILL.md` proxy
  - points the host back to the canonical package `SKILL.md`
  - captures JSON event output from `codex exec` and `codex exec resume`
- `KimiCodeHost`
  - creates a workspace-local `.kimi/skills/<package>/SKILL.md` proxy
  - runs Kimi Code through `kimi --print --output-format=stream-json`
  - uses `--work-dir`, `--add-dir`, `--skills-dir`, and `--session` so the host can read the canonical package while keeping eval artifacts isolated
  - forces UTF-8 Python subprocess output on Windows to avoid GBK failures when a skill contains Chinese text or emoji
  - runs `kimi` directly instead of through a PowerShell wrapper so normal stderr lines like `To resume this session` do not become false failures

Model selection:

- default: let Kimi CLI use the model from its own login/config state
- optional override: set `KIMI_CLI_MODEL`
- do not reuse `KIMI_CODE_MODEL` for the host lane; that variable belongs to the API endpoint path

Kimi Code note:

- Kimi Code is primarily a coding-agent product, not a generic scripted Chat Completions backend.
- The API lane can resolve `VISION_LLM_PROVIDER=kimi-code`, but Kimi's coding endpoint may reject generic direct API calls outside supported coding agents.
- For real Kimi Code skill validation, use this host lane with Kimi CLI installed and authenticated.

Current entry points:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend codex --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 4 --max-evals 4
```

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

Current extraction chain:

```text
raw host transcript
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

This lane is intentionally parallel to `toolchain.run_eval_pipeline`. It is a release-preflight validation layer, not a replacement for the API eval path.
