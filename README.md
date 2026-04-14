# Vision Skill

`vision-skill` is the current engineering workspace for the Vision skill pipeline.

This repository is not a loose collection of demo prompts. It is a local-first project for:

- turning demo-origin skills into structured packages
- running evaluation iterations with evidence on disk
- comparing `with_skill` and `without_skill`
- analyzing why a skill works or fails
- preparing human review and release decisions

## Current Submission Scope

The current repository is organized as a submission-ready `v0.1` engineering baseline.

Included in this version:

- Level 1-2 validators
- certified eval ingestion through `metadata/package.json -> eval_source`
- Level 3A gate checks and supporting benchmark pipeline
- Level 3B differential benchmark with pairwise LLM judging
- `level3-summary.json` as the normalized Level 3 handoff artifact
- Level 4 stability analysis
- Level 5 mechanism analysis
- Level 6 cognitive review packet and release recommendation
- one unified CLI: `python -m toolchain.run_eval_pipeline`
- one parallel Host Agent Eval Lane with `Codex` as the first backend
- one candidate package: `swot-analysis`
- one sample workspace with real iteration artifacts

Not yet included as a finished platform:

- batch package production at scale
- full builder/packager implementation
- multiple production-ready core packages

## Repository Layout

```text
vision-skill/
  README.md
  pyproject.toml
  docs/
  eval-factory/
  packages/
  package-workspaces/
  shared/
  reports/
  toolchain/
```

Main directories:

- `packages/`
  - canonical skill packages
- `eval-factory/`
  - certified eval upstream, scenario cards, calibration reports
- `package-workspaces/`
  - iteration evidence, benchmarks, review outputs
- `toolchain/`
  - validators, executors, graders, judges, benchmarks, analyzers, reviews, eval-factory bridge
- `shared/`
  - reusable source index, glossaries, boundary rules, review templates
- `docs/`
  - plans, specs, code understanding guides, submission overview
- `reports/`
  - project-level reports, audits, release-facing summaries

## Recommended Reading Order

If you are reviewing the project for the first time:

1. [Submission Overview](./docs/submission-ready-overview-v0.1.md)
2. [System Overview](./docs/project-plans/2026-04-08-vision-skill-mainline-a-system-overview-v0.1.md)
3. [Code Understanding Guide](./docs/code-guides/2026-04-08-vision-skill-code-understanding-guide-v0.1.md)
4. [Toolchain README](./toolchain/README.md)
5. [Eval Factory Contract](./docs/package-specs/eval-factory-contract-v0.1.md)

## Quick Start

Environment:

- Python `>=3.11`
- `pytest`
- `DASHSCOPE_API_KEY` for real model execution and Level 5 analysis

Install dev dependency:

```bash
pip install -e .[dev]
```

Run the toolchain test suite:

```bash
pytest
```

Run the default end-to-end pipeline for the reference package:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 2 --runs-per-configuration 3 --judge-model "qwen-plus" --analyzer-model "qwen-plus"
```

Run the lightweight smoke path for online verification:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 3 --smoke
```

Run the Host Agent Eval Lane against host-enabled eval cases:

```bash
python -m toolchain.agent_hosts.run_host_eval --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 4 --max-evals 4
```

Run only the supporting Level 3A gate benchmark:

```bash
python -m toolchain.benchmarks.run_benchmark --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --skill-name "SWOT Analysis" --skill-path "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

Run only the Level 3B differential benchmark:

```bash
python -m toolchain.benchmarks.run_differential_benchmark --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --skill-name "SWOT Analysis" --skill-path "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --judge-model "qwen-plus"
```

Run only Level 4-6 against the normalized Level 3 summary:

```bash
python -m toolchain.run_level456 --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

Inspect the certified eval upstream:

```bash
pytest toolchain/eval_factory/tests/test_catalog.py
```

## Current Canonical Example

The current submission keeps one canonical example package and workspace so reviewers can inspect the full pipeline without guessing:

- package: [packages/swot-analysis](./packages/swot-analysis)
- workspace: [package-workspaces/swot-analysis-workspace](./package-workspaces/swot-analysis-workspace)
- certified eval bundle: [eval-factory/certified-evals/swot-analysis/swot-analysis-certified-batch-v0.1.json](./eval-factory/certified-evals/swot-analysis/swot-analysis-certified-batch-v0.1.json)

This example is intentionally kept in the repository as the current reference package for:

- package layout
- eval layout
- benchmark artifacts
- differential benchmark artifacts
- stability output
- analysis output
- human review packet flow

## Notes For Reviewers

- This repository is currently package-factory oriented, not product-UI oriented.
- The toolchain is intentionally file-contract based. Most module boundaries are defined by files such as `eval_metadata.json`, `grading.json`, `benchmark.json`, and `analysis.json`.
- The repository now treats `differential-benchmark.json` as the primary Level 3 artifact. `benchmark.json` remains as a gate/supporting artifact.
- `level3-summary.json` is the normalized handoff from Level 3 into Level 4-6.
- package evals are now sourced from certified bundles by default when `metadata/package.json -> eval_source` is present.
- package evals may optionally include `host_eval` blocks for real-host validation.
- the host lane now writes `host-normalized-events.json`, `host-signal-report.json`, and `host-protocol-report.json` so protocol drift and host noise can be reviewed separately from raw transcripts.
- host-side prompt inputs must stay compact. Raw `host-transcript.json` and full `SKILL.md` are not valid future host-analysis inputs.
- `--smoke` is now the recommended online verification mode. It defaults to `1` run per configuration, limits scope to at most `2` evals when no explicit filter is provided, and skips completed runs so interrupted smoke jobs can be resumed.
- the repository now has a parallel Host Agent Eval Lane. The first backend is `Codex`, and it currently focuses on `trigger + multi-turn protocol` rather than full tool fidelity.
- The current example package is not yet a proven winner over baseline. That is an accurate project state, not a missing artifact.

## Next Recommended Work

- improve `swot-analysis` so `with_skill` clearly beats baseline
- use the host lane to verify that improved skills still trigger and hold protocol inside a real host
- add 2-3 more candidate packages using the same contract
- connect builder and packager modules to the current evaluation chain
