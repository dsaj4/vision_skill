# Vision Skill

`vision-skill` is a local-first engineering workspace for building, evaluating, and improving Vision skills.

It is organized around one main idea: skills should move through a repeatable production line instead of being hand-edited prompt demos.

```text
package
  -> certified evals
  -> API differential evaluation
  -> stability and mechanism analysis
  -> host-agent validation
  -> human review
  -> release-ready artifacts
```

## Current Scope

This repository is prepared as a clean engineering baseline.

Included:

- package contracts and current skill packages
- certified eval ingestion through `metadata/package.json -> eval_source`
- unified API evaluation CLI: `python -m toolchain.run_eval_pipeline`
- Level 3 differential benchmark with `level3-summary.json`
- Level 4 stability analysis
- Level 5 mechanism analysis
- Level 6 human review packet and release recommendation
- parallel host-agent validation with `Codex` and `Kimi Code`
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
2. [Toolchain README](./toolchain/README.md)
3. [Eval Factory README](./eval-factory/README.md)
4. [Packages README](./packages/README.md)

## Quick Start

Environment:

- Python `>=3.11`
- `pytest`
- a provider API key for real model execution
- optional Kimi CLI for Kimi Code host validation

Install dev dependencies:

```bash
pip install -e .[dev]
```

Run tests:

```bash
python -m pytest
```

Run the default API evaluation pipeline:

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

- `differential-benchmark.json` is the primary Level 3 value signal.
- `benchmark.json` remains a supporting gate artifact.
- `level3-summary.json` is the normalized handoff into Level 4-6.
- package evals can be synced from certified bundles by default.
- host evals are parallel release evidence focused on trigger and multi-turn protocol behavior.
- generated workspaces under `package-workspaces/*-workspace/` are local artifacts and should not be committed.
- this baseline does not claim every package already beats its baseline; quality promotion remains evidence-driven.
