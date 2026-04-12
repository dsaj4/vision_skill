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
- Level 3 grading and benchmark pipeline
- Level 4 stability analysis
- Level 5 mechanism analysis
- Level 6 cognitive review packet and release recommendation
- one candidate package: `swot-analysis`
- one sample workspace with real iteration artifacts

Not yet included as a finished platform:

- batch package production at scale
- full builder/packager implementation
- a unified end-to-end CLI for every stage
- multiple production-ready core packages

## Repository Layout

```text
vision-skill/
  README.md
  pyproject.toml
  docs/
  packages/
  package-workspaces/
  shared/
  reports/
  toolchain/
```

Main directories:

- `packages/`
  - canonical skill packages
- `package-workspaces/`
  - iteration evidence, benchmarks, review outputs
- `toolchain/`
  - validators, executors, graders, benchmarks, analyzers, reviews
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

Rebuild benchmark artifacts for the sample workspace:

```bash
python -m toolchain.benchmarks.run_benchmark --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --skill-name "SWOT Analysis" --skill-path "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

Run Level 4-6 post-benchmark processing:

```bash
python -m toolchain.run_level456 --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

## Current Canonical Example

The current submission keeps one canonical example package and workspace so reviewers can inspect the full pipeline without guessing:

- package: [packages/swot-analysis](./packages/swot-analysis)
- workspace: [package-workspaces/swot-analysis-workspace](./package-workspaces/swot-analysis-workspace)

This example is intentionally kept in the repository as the current reference package for:

- package layout
- eval layout
- benchmark artifacts
- stability output
- analysis output
- human review packet flow

## Notes For Reviewers

- This repository is currently package-factory oriented, not product-UI oriented.
- The toolchain is intentionally file-contract based. Most module boundaries are defined by files such as `eval_metadata.json`, `grading.json`, `benchmark.json`, and `analysis.json`.
- The current example package is not yet a proven winner over baseline. That is an accurate project state, not a missing artifact.

## Next Recommended Work

- improve `swot-analysis` so `with_skill` clearly beats baseline
- add 2-3 more candidate packages using the same contract
- connect builder and packager modules to the current evaluation chain
