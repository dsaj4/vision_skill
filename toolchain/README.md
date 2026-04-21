# Toolchain

This directory contains the current engineering toolchain for `vision-skill`.

## Current Modules

- `validators/`
  - Level 1-2
  - package structure and protocol checks
- `executors/`
  - run `with_skill / without_skill` executions
- `graders/`
  - Level 3A gate checks and legacy grading
- `judges/`
  - Level 3B pairwise differential judging
- `benchmarks/`
  - legacy benchmark aggregation, differential benchmark, and stability
- `analyzers/`
  - Level 5 mechanism analysis
- `reviews/`
  - Level 6 review packet and release recommendation
- `eval_factory/`
  - validate and export certified eval bundles
  - sync certified bundles into package evals for mainline consumption
- `kimi_cycle/`
  - Codex-controlled Kimi production loop
  - generates eval drafts, rewrites skills, and triggers the next Kimi eval round
- `agent_hosts/`
  - real host validation
  - current backends: `Codex`, `Kimi Code`
  - validates skill trigger and multi-turn protocol outside the API lane

Still placeholder modules:

- `builders/`
- `packagers/`

## Reading Order

1. `validators/`
2. `executors/`
3. `graders/`
4. `judges/`
5. `benchmarks/`
6. `analyzers/`
7. `reviews/`
8. `eval_factory/`
9. `kimi_cycle/`
10. `agent_hosts/`

## Common Commands

Set the model provider. The default is DashScope. For Kimi Code:

```powershell
$env:VISION_LLM_PROVIDER="kimi-code"
$env:KIMI_CODE_BASE_URL="https://api.kimi.com/coding/v1"
$env:KIMI_CODE_MODEL="kimi-for-coding"
$env:KIMI_CODE_API_KEY="<your-kimi-code-key>"
```

Kimi Code note: the coding endpoint is intended for supported coding agents. If direct API calls are rejected, keep the API lane on DashScope or Moonshot and run Kimi Code through the host lane below.

Run the default end-to-end eval pipeline:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 2 --runs-per-configuration 3 --judge-model "qwen-plus" --analyzer-model "qwen-plus"
```

Run the lightweight smoke path:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 3 --smoke
```

Smoke mode behavior:

- defaults to `1` run per configuration
- defaults to at most `2` evals when no `--eval-ids` or `--max-evals` is supplied
- enables `skip_completed` automatically so interrupted smoke jobs can resume without re-running finished calls

Run the host lane for host-enabled eval cases:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend codex --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 4 --max-evals 4
```

Run the host lane through Kimi Code CLI:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 4 --max-evals 4
```

Run the Codex-controlled Kimi production loop:

```bash
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\golden-circle" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\golden-circle-workspace" --apply-generated-evals --apply-skill --run-eval
```

Run the supporting Level 3A gate benchmark:

```bash
python -m toolchain.benchmarks.run_benchmark --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --skill-name "SWOT Analysis" --skill-path "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

Run the new differential benchmark path:

```bash
python -m toolchain.benchmarks.run_differential_benchmark --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --skill-name "SWOT Analysis" --skill-path "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --judge-model "qwen3.5-plus"
```

Run Level 4-6 against the normalized `level3-summary.json` handoff:

```bash
python -m toolchain.run_level456 --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

Validate the current eval-factory sample bundle:

```bash
pytest toolchain/eval_factory/tests/test_catalog.py
```

## Current Differential Outputs

The new Level 3B path writes these artifacts in the iteration directory:

- `pairwise-judgment.json`
- `pairwise-judgment-reversed.json`
- `pairwise-consensus.json`
- `differential-benchmark.json`
- `differential-benchmark.md`

These remain on disk alongside the older `benchmark.json` gate artifact, but the mainline now treats `differential-benchmark.json` as the Level 3 primary output.

## Current Mainline Contract

The default eval path is now:

```text
certified bundle
  -> package eval sync
  -> prepare iteration
  -> execute
  -> benchmark.json (gate/supporting)
  -> differential-benchmark.json (primary)
  -> level3-summary.json
  -> stability
  -> analysis
  -> human review packet
  -> release recommendation
```

Level 4-6 should read `level3-summary.json` first, not `benchmark.json` directly.

The host lane runs in parallel:

```text
package evals with host_eval.enabled
  -> Codex host proxy
  -> host transcript
  -> normalized events
  -> signal report
  -> protocol report
  -> trigger report
  -> host grading
  -> host-benchmark.json
```

The host lane is rule-first:

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
