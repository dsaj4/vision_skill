# Agent Hosts

This module contains the real host-eval lane.

Current purpose:

- verify that a skill is discoverable inside a real host
- verify that multi-turn protocol behavior survives the host layer
- keep host evidence separate from the API eval lane
- extract richer rule-based host signals without sending raw transcripts to a model

Current backend:

- `CodexHost`
  - creates a workspace-local `.codex/skills/<package>/SKILL.md` proxy
  - points the host back to the canonical package `SKILL.md`
  - captures JSON event output from `codex exec` and `codex exec resume`

Current entry point:

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
