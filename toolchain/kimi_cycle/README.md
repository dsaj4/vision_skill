# Kimi Cycle

This module contains the Codex-controlled Kimi production loop.

Purpose:

- generate the next package-local eval draft through Kimi CLI
- generate the next skill rewrite draft through Kimi CLI
- keep Codex as the controller that validates, applies, and decides whether to run the next evaluation round
- keep all draft artifacts in a dedicated cycle directory for traceability

Current design:

```text
Codex controller
  -> Kimi eval generation draft
  -> optional apply to package evals/evals.json
  -> Kimi skill rewrite draft
  -> Codex validation
  -> optional apply to package SKILL.md + demo mirror
  -> Kimi differential eval
  -> optional Kimi host validation
  -> cycle summary
```

Key rule:

- Kimi generates
- Codex validates and orchestrates
- package state changes only happen through Codex-controlled apply steps
