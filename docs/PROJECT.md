# Vision Skill Project Overview

Last updated: 2026-04-24

## Purpose

`vision-skill` is a local-first engineering workspace for building, evaluating, improving, and packaging Vision skills.

The project is not a prompt demo archive. Its current goal is to provide a repeatable production line:

```text
demo-origin package
  -> certified evals
  -> API differential evaluation
  -> stability and mechanism analysis
  -> real host validation
  -> human review
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

Not included:

- committed model transcripts or benchmark run outputs
- historical planning document sprawl
- generated Kimi/Codex workspace bundles
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

The API evaluation lane is the low-cost, repeatable screening path.

```text
certified bundle
  -> package eval sync
  -> prepare iteration
  -> execute with_skill / without_skill
  -> benchmark.json as supporting gate
  -> differential-benchmark.json as Level 3 primary result
  -> level3-summary.json as normalized handoff
  -> stability.json
  -> analysis.json
  -> human-review-packet.md
  -> release-recommendation.json
```

Important rules:

- `differential-benchmark.json` is the primary Level 3 value signal.
- `benchmark.json` is retained as a supporting gate artifact.
- Level 4-6 modules should read `level3-summary.json` first.
- Workspace artifacts are generated locally under `package-workspaces/*-workspace/` and are ignored by git.

## Host Agent Lane

The host lane checks whether a real agent can trigger and execute a skill protocol.

Current backends:

- `codex`
- `kimi-code`

The host lane is parallel evidence. It does not replace the API lane.

```text
host-enabled eval case
  -> host adapter
  -> raw transcript
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

## Release Hygiene

The cleaned release tree follows these rules:

- keep code, package sources, certified evals, and stable docs
- remove generated run workspaces before submission
- keep `package-workspaces/README.md` only as the runtime artifact contract
- keep `.env` and API keys out of git
- ignore local exports and prompt scratch files
- treat docs in this directory as the release-facing truth

## Basic Commands

Install for development:

```bash
pip install -e .[dev]
```

Run tests:

```bash
python -m pytest
```

Run the unified API evaluation pipeline:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --runs-per-configuration 3
```

Run a smoke evaluation:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --smoke
```

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
