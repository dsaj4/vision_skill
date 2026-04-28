# Vision Skill Project Overview

Last updated: 2026-04-25

## Purpose

`vision-skill` is a local-first engineering workspace for building, evaluating, improving, and packaging Vision skills.

The project is not a prompt demo archive. Its current goal is to provide a repeatable production line:

```text
demo-origin package
  -> certified evals
  -> Kimi Code execution
  -> hard gate
  -> quantitative supporting bundle
  -> deep quality evaluation
  -> Kimi host validation
  -> agent review report
  -> human authorization
  -> release-ready skill artifacts
```

## Current Release Shape

The repository is prepared as an engineering baseline. It keeps source files, package definitions, certified eval inputs, and toolchain code. Generated run artifacts are excluded from version control.

Included:

- canonical packages under `packages/`
- certified eval upstream under `eval-factory/`
- local evaluation and review toolchain under `toolchain/`
- shared templates and source indexes under `shared/`
- minimal release-facing documentation under `docs/`
- centralized helper/runtime modules: `toolchain/common.py`, `toolchain/kimi_runtime.py`, and `toolchain/kimi_workspace.py`

Not included:

- committed model transcripts or benchmark run outputs
- historical planning document sprawl
- generated Kimi workspace bundles
- local exports and cache folders

## Package Coverage

Current package directories:

- `swot-analysis`
- `golden-circle`
- `pyramid-principle`
- `mece-analysis`
- `first-principles`
- `five-whys`

`swot-analysis` remains the reference package for the complete evaluation path. The thinking-model packages are active candidates and should be evaluated or improved through the same pipeline before release claims are made.

## Main Evaluation Lane

The main evaluation lane now runs on Kimi Code/Kimi CLI.

```text
certified bundle
  -> package eval sync
  -> prepare iteration
  -> execute scripted single-turn or multi-turn with_skill / without_skill through Kimi Code workspace-file tasks
  -> hard-gate.json
  -> quantitative-summary.json as supporting diagnostics
  -> deep-eval.json as primary quality judgment
  -> human-review-packet.md
  -> human-review-authorization.json
  -> release-recommendation.json
```

Important rules:

- `hard-gate.json` only checks whether artifacts are complete enough to evaluate.
- `deep-eval.json` is the primary quality judgment.
- `quantitative-summary.json`, `benchmark.json`, `differential-benchmark.json`, `level3-summary.json`, and `stability.json` are supporting diagnostics.
- `human-review-packet.md` is now an LLM-readable reviewer report generated from `agent-review-report.json`.
- `human-review-authorization.json` is the canonical human approval artifact. Without explicit authorization, do not claim release-ready.
- Kimi terminal text is never the mainline result source. Each execution turn reads `outputs/assistant.md`; the run-level final response is `outputs/final_response.md`; the last assistant answer is `outputs/latest_assistant_response.md`; pairwise judging reads `outputs/judgment.json`; deep quality evaluation reads `outputs/deep-eval.json`.
- `execution_eval.turn_script` is the mainline scripted multi-turn source. `host_eval.turn_script` is reserved for real host validation, with only legacy fallback support in the executor.
- Workspace artifacts are generated locally under `package-workspaces/*-workspace/` and are ignored by git.

## Kimi Host Validation

Kimi host validation checks whether the real Kimi Code host can trigger and execute a skill protocol.

Current backend:

- `kimi-code`

```text
host-enabled eval case
  -> KimiCodeHost
  -> raw Kimi transcript
  -> normalized events
  -> signal report
  -> protocol report
  -> trigger report
  -> host benchmark
```

Host information extraction is rule-first:

- clean raw transcript mechanically before extraction
- normalize events
- extract trigger, routing, protocol, structure, and host-interference signals
- classify protocol path with a state-machine-style classifier
- keep raw transcripts as evidence, but do not feed full transcripts into future model prompts

## Kimi Production Cycle

Codex remains the controller for each production iteration. Kimi Code is used as a worker or host backend, not as the project coordinator.

The intended loop is:

```text
Codex prepares a bounded workspace packet
  -> Kimi reads task files in the workspace
  -> Kimi writes required outputs under outputs/
  -> Codex validates and normalizes outputs
  -> Codex applies accepted changes
  -> Codex runs evals and decides the next iteration
```

Kimi prompts should be compact and file-oriented. Instead of asking Kimi to return large JSON or full `SKILL.md` content in chat, the controller writes:

- `task.md`
- `workspace-manifest.json`
- compact `inputs/package-packet.json`
- compact `inputs/recent-context.json`
- truncated `inputs/current-skill.md`
- truncated `inputs/examples.md`
- `contracts/output-contract.md`
- output examples under `examples/`

Kimi should edit or create files in the assigned workspace and keep terminal responses short.

The same controlled workspace-file contract now applies to the evaluation mainline:

- executor turn task: `task.md -> outputs/assistant.md`
- pairwise judge task: `inputs/pairwise-packet.json -> outputs/judgment.json`
- deep quality eval task: `inputs/deep-eval-packet.json -> outputs/deep-eval.json`

## Release Hygiene

The cleaned release tree follows these rules:

- keep code, package sources, certified evals, and stable docs
- remove generated run workspaces before submission
- keep `package-workspaces/README.md` only as the runtime artifact contract
- keep `.env` and API keys out of git
- ignore local exports and prompt scratch files
- treat docs in this directory as the release-facing truth
- avoid placeholder directories in the release tree; add a module only when it has executable code or a stable contract

## Basic Commands

Install for development:

```bash
pip install -e .[dev]
```

Run tests:

```bash
python -m pytest
```

Run the unified Kimi Code evaluation pipeline:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1
```

Run a smoke evaluation:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --smoke
```

The unified Kimi Code pipeline is the default evaluation entrypoint. Lower-level benchmark, Level 4-6, and host commands are kept for targeted debugging, compatibility, and release validation rather than everyday package screening.

By default the pipeline uses the fast iteration profile: `1` run per configuration and single-pass pairwise judging. Use `--thorough` only when you need slower stability evidence: it restores `3` runs per configuration and balanced pairwise judging.

Run host validation:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --max-evals 4
```

Run a Codex-controlled Kimi production cycle:

```bash
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\golden-circle" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\golden-circle-workspace" --apply-generated-evals --apply-skill --run-eval
```

## Current Status

The repository is ready as a clean engineering baseline. It is not a claim that every package already beats baseline. Each skill still needs evidence-backed improvement through the evaluation loop before being promoted as a release-quality skill.
