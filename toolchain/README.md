# Toolchain

This directory contains the current engineering toolchain for `vision-skill`.

## Current Modules

- `validators/`
  - Level 1-2
  - package structure and protocol checks
- `executors/`
  - run `with_skill / without_skill` executions through Kimi Code
- `graders/`
  - legacy rule grading used by the quantitative bundle
- `judges/`
  - pairwise differential judging used by the quantitative bundle
- `benchmarks/`
  - legacy benchmark aggregation, differential benchmark, and stability
- `hard_gates/`
  - run artifact completeness checks before quality evaluation
- `quantitative/`
  - supporting quantitative bundle over grading, differential, Level 3 summary, and stability
- `deep_evals/`
  - primary content-quality evaluation over raw model answers and run artifacts
- `analyzers/`
  - legacy mechanism analysis compatibility path
- `reviews/`
  - agent review report, human authorization, and release recommendation
- `eval_factory/`
  - validate and export certified eval bundles
  - sync certified bundles into package evals for mainline consumption
- `kimi_cycle/`
  - Codex-controlled Kimi production loop
  - generates eval drafts, rewrites skills, and triggers the next Kimi eval round
- `agent_hosts/`
  - Kimi Code host validation
  - validates skill trigger and multi-turn protocol in the real Kimi host
- `common.py`
  - shared JSON/text, eval-id, slug, JSON extraction, and text budget helpers
- `kimi_runtime.py`
  - canonical Kimi CLI command, environment, JSONL, assistant-message, and session parsing helpers
- `kimi_workspace.py`
  - canonical controlled workspace-file task runtime for Kimi execution, judging, and analysis

## Reading Order

1. `validators/`
2. `executors/`
3. `graders/`
4. `judges/`
5. `benchmarks/`
6. `hard_gates/`
7. `quantitative/`
8. `deep_evals/`
9. `reviews/`
10. `eval_factory/`
11. `kimi_cycle/`
12. `agent_hosts/`
13. `common.py`, `kimi_runtime.py`, and `kimi_workspace.py` when changing shared helper behavior

## Common Commands

Set the optional Kimi CLI model override:

```powershell
$env:KIMI_CLI_MODEL="kimi-for-coding"
```

If `KIMI_CLI_MODEL` is not set, the toolchain lets the logged-in Kimi CLI use its configured default model.

Run the default Kimi Code eval pipeline:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 2 --model "kimi-for-coding" --judge-model "kimi-for-coding" --analyzer-model "kimi-for-coding"
```

Default behavior is optimized for fast iteration:

- `1` run per configuration
- single-pass pairwise judging
- full hard gate, quantitative summary, deep eval, review packet, and release recommendation still generated
- package snapshot artifacts also generated so the latest `SKILL.md` is easy to open from the workspace

Run the slower stability-oriented profile only when needed:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 2 --thorough --model "kimi-for-coding" --judge-model "kimi-for-coding" --analyzer-model "kimi-for-coding"
```

Run the lightweight smoke path:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 3 --smoke
```

Smoke mode behavior:

- defaults to `1` run per configuration
- defaults to at most `2` evals when no `--eval-ids` or `--max-evals` is supplied
- enables `skip_completed` automatically so interrupted smoke jobs can resume without re-running finished calls

The commands above are the recommended mainline entrypoints. Prefer them unless you are debugging a specific lower-level module.

Run Kimi Code host validation for host-enabled eval cases:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 4 --max-evals 4
```

Run the Codex-controlled Kimi production loop:

```bash
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\golden-circle" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\golden-circle-workspace" --apply-generated-evals --apply-skill --run-eval
```

## Advanced/Internal Compatibility Commands

The following commands are kept for targeted debugging and backwards compatibility. They are not the default project workflow.

Run the supporting Level 3A gate benchmark:

```bash
python -m toolchain.benchmarks.run_benchmark --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --skill-name "SWOT Analysis" --skill-path "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

Run the new differential benchmark path:

```bash
python -m toolchain.benchmarks.run_differential_benchmark --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --skill-name "SWOT Analysis" --skill-path "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --judge-model "kimi-for-coding"
```

The differential benchmark defaults to single-pass judging. Add `--balanced-judging` when you explicitly need the slower forward + reversed check.

Run the supporting quantitative bundle:

```bash
python -m toolchain.quantitative.run_quantitative_bundle --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --judge-model "kimi-for-coding"
```

Run deep quality evaluation directly:

```bash
python -m toolchain.deep_evals.run_deep_eval --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --deep-eval-model "kimi-for-coding"
```

Run the post-execution compatibility pipeline on an already executed iteration:

```bash
python -m toolchain.run_level456 --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

This compatibility entry now follows the refactored flow: `hard gate -> quantitative summary -> deep eval -> review`. It no longer treats `analysis.json` or `level3-summary.json` as required primary inputs.

Validate the current eval-factory sample bundle:

```bash
pytest toolchain/eval_factory/tests/test_catalog.py
```

## Current Quantitative Outputs

The quantitative bundle writes these artifacts in the iteration directory:

- `pairwise-judgment.json`
- `pairwise-judgment-reversed.json` (empty in the default single-pass profile)
- `pairwise-consensus.json`
- `benchmark.json`
- `differential-benchmark.json`
- `differential-benchmark.md`
- `level3-summary.json`
- `stability.json`
- `quantitative-summary.json`
- `quantitative-summary.md`

These remain on disk for diagnostics and compatibility, but the mainline now treats them as supporting evidence. `deep-eval.json` is the primary quality judgment artifact.

## Current Mainline Contract

The default eval path is now:

```text
certified bundle
  -> package eval sync
  -> prepare iteration
  -> package snapshot (iteration package/ + workspace latest-package/ + latest-skill.md)
  -> execute with Kimi Code workspace-file tasks, including scripted multi-turn when `execution_eval.turn_script` exists
  -> hard-gate.json
  -> quantitative-summary.json (supporting bundle, including old benchmark/differential/stability artifacts)
  -> deep-eval.json through workspace-file tasks
  -> agent-review-report.json
  -> human-review-packet.md
  -> human-review-authorization.json
  -> release recommendation
```

Review and recommendation should read `deep-eval.json` first. `human-review-packet.md` is now rendered as an LLM-readable report from `agent-review-report.json`, and `human-review-authorization.json` is the canonical human approval artifact. `level3-summary.json`, `benchmark.json`, `differential-benchmark.json`, and `stability.json` remain supporting diagnostics.

Package snapshot artifacts:

- `iteration-N/package/`
  - immutable snapshot of the package state used by that iteration
- `package-workspaces/<package>-workspace/latest-package/`
  - stable latest package snapshot path
- `package-workspaces/<package>-workspace/latest-skill.md`
  - stable direct copy of the latest `SKILL.md`
- `package-workspaces/upload-ready-skills/<package>/SKILL.md`
  - pure upload-ready skill folder, containing only the current `SKILL.md` for each package
- `package-workspaces/upload-ready-skills/index.json`
  - index of all currently exported pure-skill upload folders

Runtime profile:

- default: fast iteration, `1` run per configuration, single-pass pairwise judge
- `--thorough`: slower stability profile, `3` runs per configuration, balanced pairwise judge
- `--balanced-judging`: only switch pairwise judge to forward + reversed while keeping the selected run count

Mainline Kimi calls no longer consume large terminal replies as results:

- executor per-turn source: `outputs/assistant.md`
- executor run source: `outputs/final_response.md` as the full conversation transcript
- executor latest answer source: `outputs/latest_assistant_response.md`
- pairwise judge result source: `outputs/judgment.json`
- deep quality evaluator result source: `outputs/deep-eval.json`
- terminal output is retained only as debug log in raw artifacts

Execution eval scripts:

- `execution_eval.turn_script` is the mainline multi-turn script source for `execute_iteration`.
- `host_eval.turn_script` is for real host validation. The executor keeps a temporary fallback to it for legacy evals only.
- `final_response.md` intentionally contains the full conversation, so quantitative and pairwise checks evaluate the scripted user experience.
- `latest_assistant_response.md` is available when a downstream step needs only the final assistant answer.

Kimi host validation can also run directly on host-enabled evals:

```text
package evals with host_eval.enabled
  -> Kimi skill proxy
  -> Kimi host transcript
  -> normalized events
  -> signal report
  -> protocol report
  -> trigger report
  -> host grading
  -> host-benchmark.json
```

Host evidence extraction is rule-first:

- simple cleaning before any downstream use
- no raw host transcript in future model prompts
- compact packets only, with fixed budget caps

The new Kimi production loop sits one layer above both lanes:

```text
Codex controller
  -> prepare workspace task bundle
  -> Kimi reads workspace docs and writes outputs/
  -> Codex normalizes and validates outputs
  -> Codex validation and apply
  -> Kimi differential eval
  -> optional Kimi host validation
```

For generation stages, Kimi no longer needs to return the full eval JSON or full `SKILL.md` in the terminal response. Codex now prepares a bounded workspace task with:

- `task.md`
- `workspace-manifest.json`
- compact `inputs/package-packet.json`
- compact `inputs/recent-context.json`
- truncated `inputs/current-skill.md`
- truncated `inputs/examples.md`
- `contracts/output-contract.md`
- output examples under `examples/`

Kimi is prompted to read those files and write only the required files under `workspace/outputs/`. This keeps prompts short, makes multi-step file reading possible, and preserves a strict artifact contract for downstream validation.

## Current Eval Factory Output

The first live certified bundle currently sits outside package directories:

- `eval-factory/certified-evals/swot-analysis/swot-analysis-certified-batch-v0.1.json`

This keeps eval production separate from package consumption while still supporting package-level auto-sync through `metadata/package.json -> eval_source`.
