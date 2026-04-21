# Kimi Cycle

This module contains the Codex-controlled Kimi production loop.

Purpose:

- generate the next package-local eval draft through Kimi CLI
- generate the next skill rewrite draft through Kimi CLI
- let Kimi operate as a coding agent inside a controlled workspace instead of returning the whole artifact in terminal text
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

## Workspace Task Protocol

The generation stages no longer depend on "return the full JSON/markdown in stdout".

Instead, each stage creates a workspace bundle like this:

```text
cycle-stage/
  workspace/
    task.md
    workspace-manifest.json
    inputs/
      package-packet.json
      recent-context.json
      current-skill.md
      current-evals.json
      examples.md
    contracts/
      output-contract.md
    examples/
      *.example.json / *.example.md
    outputs/
      ...
```

Codex writes the bundle first. Kimi is then prompted to:

1. read `task.md`
2. read `workspace-manifest.json`
3. read the listed input, contract, and example files
4. write only the required files under `outputs/`
5. return a short completion note

This gives Kimi file-editing freedom inside a bounded workspace while keeping the final contract machine-checkable.

## Stage Outputs

Eval generation writes:

- `workspace/outputs/eval-draft.json`
- `workspace/outputs/run-report.json`

Skill rewrite writes:

- `workspace/outputs/SKILL.generated.md`
- `workspace/outputs/run-report.json`

Codex then reads those files, normalizes them, runs validators, and decides whether to apply them back into the package.
