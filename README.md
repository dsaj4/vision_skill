# Vision Skill

`vision-skill` is a local-first engineering workspace for building, evaluating, and improving Vision skills.

It is organized around one main idea: skills should move through a repeatable production line instead of being hand-edited prompt demos.

```text
package
  -> certified evals
  -> Kimi Code execution
  -> hard gate
  -> quantitative supporting bundle
  -> deep quality evaluation
  -> Kimi host validation
  -> human review
  -> release-ready artifacts
```

## Current Scope

This repository is prepared as a clean engineering baseline.

Included:

- package contracts and current skill packages
- certified eval ingestion through `metadata/package.json -> eval_source`
- unified Kimi Code evaluation CLI: `python -m toolchain.run_eval_pipeline`
- hard gate checks with `hard-gate.json`
- supporting quantitative bundle with legacy `benchmark.json`, `differential-benchmark.json`, `level3-summary.json`, and `stability.json`
- deep quality evaluation with `deep-eval.json`, `deep-eval.md`, and `quality-failure-tags.json`
- human review packet and release recommendation based on hard gate + deep eval + human decision
- Kimi Code host validation
- Codex-controlled Kimi production-cycle support

Not included in version control:

- generated run workspaces
- raw model transcripts
- temporary exports
- local cache folders
- historical planning-note sprawl

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
  toolchain/
```

Main directories:

- `docs/`: release-facing project documentation
- `eval-factory/`: certified eval upstream and bundle contracts
- `packages/`: canonical skill packages
- `package-workspaces/`: local runtime artifact root, ignored except for its README
- `shared/`: reusable templates, indexes, and review assets
- `toolchain/`: validators, executors, graders, judges, benchmarks, analyzers, reviews, host adapters, and Kimi cycle tools

## Recommended Reading

1. [Project Overview](./docs/PROJECT.md)
2. [Structure And Functions](./docs/STRUCTURE_AND_FUNCTIONS.md)
3. [Eval Flow Before And After Comparison](./docs/EVAL_FLOW_BEFORE_AFTER_COMPARISON.md)
4. [Eval System Refactor Plan V1](./docs/EVAL_SYSTEM_REFACTOR_PLAN_V1.md)
5. [Darwin Rubric And Flow Adaptation V1](./docs/DARWIN_RUBRIC_AND_FLOW_ADAPTATION_V1.md)
6. [Agent Skill Development Guide](./docs/AGENT_SKILL_DEVELOPMENT_GUIDE.md)
7. [Toolchain README](./toolchain/README.md)
8. [Eval Factory README](./eval-factory/README.md)
9. [Packages README](./packages/README.md)

## Quick Start

Environment:

- Python `>=3.11`
- `pytest`
- Kimi CLI installed and logged in

Install dev dependencies:

```bash
pip install -e .[dev]
```

Run tests:

```bash
python -m pytest
```

Run the default Kimi Code evaluation pipeline:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --runs-per-configuration 3
```

Run a lightweight smoke pass:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --smoke
```

Run host-agent validation through Kimi Code:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --max-evals 4
```

Run the Codex-controlled Kimi production loop:

```bash
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\golden-circle" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\golden-circle-workspace" --apply-generated-evals --apply-skill --run-eval
```

## Current Packages

- [swot-analysis](./packages/swot-analysis)
- [golden-circle](./packages/golden-circle)
- [pyramid-principle](./packages/pyramid-principle)
- [mece-analysis](./packages/mece-analysis)
- [first-principles](./packages/first-principles)
- [five-whys](./packages/five-whys)

`swot-analysis` is the current reference package for the full evaluation path. Other packages are active candidates and should be promoted only after evidence-backed evaluation.

## Release Notes

- `hard-gate.json` decides whether run artifacts are complete enough for quality evaluation.
- `deep-eval.json` is now the primary quality judgment artifact.
- `quantitative-summary.json` packages old quantitative signals as supporting evidence.
- `benchmark.json`, `differential-benchmark.json`, `level3-summary.json`, and `stability.json` are retained for diagnostics and compatibility.
- shared helper code now lives in `toolchain/common.py`; Kimi CLI runtime behavior is centralized in `toolchain/kimi_runtime.py`; Kimi workspace-file task execution is centralized in `toolchain/kimi_workspace.py`.
- the Kimi mainline treats terminal replies as logs only: executor output comes from `outputs/assistant.md`, pairwise judgment from `outputs/judgment.json`, and deep quality judgment from `outputs/deep-eval.json`.
- package evals can be synced from certified bundles by default.
- Kimi host evals are release evidence focused on trigger and multi-turn protocol behavior.
- generated workspaces under `package-workspaces/*-workspace/` are local artifacts and should not be committed.
- this baseline does not claim every package already beats its baseline; quality promotion remains evidence-driven.
