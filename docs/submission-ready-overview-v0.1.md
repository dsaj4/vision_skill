# Vision Skill Submission Overview V0.1

## Purpose

This document explains what the repository currently contains, what has been cleaned for submission, and how a reviewer should understand the current project state.

## What This Submission Is

This submission is a `v0.1` engineering baseline for the Vision skill pipeline.

It is meant to show:

- the project structure
- the package contract
- the eval-factory contract
- the evaluation chain
- the current example package
- the evidence model for iteration and review

It is not meant to claim that the whole Vision skill system is already complete.

## What Was Cleaned For Submission

The repository has been organized around a small set of canonical entry points:

- root-level `README.md`
- `pyproject.toml` for basic project metadata and pytest configuration
- `.gitignore` for cache and local raw-material cleanup
- `docs/README.md` as the documentation index
- the existing toolchain and sample package/workspace as the primary review targets

Repository noise intentionally excluded from commit scope:

- Python cache directories
- pytest cache
- local raw material folder `思维模型/`
- local archive `思维模型.zip`

## Canonical Review Targets

Reviewers should treat the following as the current canonical paths:

- project entry: `README.md`
- docs entry: `docs/README.md`
- system overview: `docs/project-plans/2026-04-08-vision-skill-mainline-a-system-overview-v0.1.md`
- package contract: `docs/package-specs/package-contract-v0.1.md`
- code guide: `docs/code-guides/2026-04-08-vision-skill-code-understanding-guide-v0.1.md`
- sample package: `packages/swot-analysis/`
- sample workspace: `package-workspaces/swot-analysis-workspace/`
- certified eval upstream: `eval-factory/certified-evals/swot-analysis/`

## Current Implemented Scope

Implemented modules:

- Level 1
  - package structure validation
- Level 2
  - protocol validation
- Level 3
  - Level 3A gate checks and legacy benchmark aggregation
  - Level 3B differential benchmark with pairwise judging
- Level 4
  - stability analysis
- Level 5
  - mechanism analysis with model-assisted reasoning
- Level 6
  - human review packet generation and release recommendation
- Host Agent Eval Lane
  - `Codex` host adapter
  - real-host trigger validation
  - multi-turn protocol validation

Current sample assets:

- `swot-analysis` candidate package
- first certified eval bundle for `swot-analysis`
- one workspace with benchmark, differential benchmark, `level3-summary`, stability, analysis, and review artifacts
- host-enabled eval cases for `swot-analysis`

## Known Limits

These are current project limits and should be read as honest scope boundaries:

- only one candidate package is currently included
- builder and packager modules are still placeholders
- the current sample package does not yet consistently outperform baseline
- release recommendation is intentionally conservative and keeps human review as the final gate
- host lane is currently parallel evidence and has not yet been merged into the main release recommendation artifact

## How To Demo The Repository

Minimal demo path:

1. Read `README.md`
2. Inspect `packages/swot-analysis/`
3. Inspect `eval-factory/certified-evals/swot-analysis/swot-analysis-certified-batch-v0.1.json`
4. Inspect `package-workspaces/swot-analysis-workspace/iteration-1/benchmark.md`
5. Inspect `package-workspaces/swot-analysis-workspace/iteration-1/differential-benchmark.md`
6. Inspect `package-workspaces/swot-analysis-workspace/iteration-1/stability.md`
7. Inspect `package-workspaces/swot-analysis-workspace/iteration-1/analysis.md`
8. Inspect `package-workspaces/swot-analysis-workspace/iteration-1/human-review-packet.md`

Command demo path:

1. Run `pytest`
2. Run `python -m toolchain.run_eval_pipeline --smoke`
3. Run `python -m toolchain.agent_hosts.run_host_eval --max-evals 2`
4. Confirm the generated iteration contains `benchmark.json`, `differential-benchmark.json`, `level3-summary.json`, `stability.json`, `analysis.json`, and `release-recommendation.json`
5. Confirm host artifacts contain `host-transcript.json`, `host-trigger-report.json`, and `host-benchmark.json`
6. Run `pytest toolchain/eval_factory/tests/test_catalog.py`

## Recommended Submission Narrative

The cleanest way to present this repository is:

1. This is the first engineering baseline of a local-first Vision skill factory.
2. The repository already demonstrates a full evidence-based evaluation loop.
3. The current package set is intentionally small so the contract can stabilize before scale-up.
4. The current example is valuable because it exposes real weaknesses, not because it already wins.

## Next Step After Submission

- add two more candidate packages
- improve the current sample package until benchmark delta is meaningfully positive
- connect the future builder/packager layers to the current evaluation chain
