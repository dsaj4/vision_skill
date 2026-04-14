# Eval Factory Contract V0.1

## Purpose

This document explains the current file contract for `eval-factory/`.

`v0.1` keeps the design intentionally lightweight:

- file-based only
- no database
- one certified bundle can be validated independently
- certified bundles can be exported into package-style `evals.json`

## Current Flow

```text
source-bank
  -> scenario-cards
  -> eval-candidates
  -> calibration-reports
  -> certified-evals
```

The current bridge into the package mainline is:

```text
certified-evals
  -> toolchain.eval_factory.sync_package_evals(...)
  -> toolchain.eval_factory.resolve_package_evals(...)
  -> package evals.json
```

Package declaration lives in `metadata/package.json`:

```json
{
  "eval_source": {
    "mode": "certified-bundle",
    "bundle_path": "../../eval-factory/certified-evals/<package>/<bundle>.json",
    "sync_on_read": true,
    "sync_output": "evals/evals.json"
  }
}
```

## Directory Contract

### `source-bank/`

Stores the raw upstream material.

Required fields:

- `source_id`
- `task_family`
- `raw_text`
- `source_type`
- `notes`

### `scenario-cards/`

Turns raw material into a reusable task abstraction.

Required fields:

- `scenario_id`
- `task_family`
- `source_ids`
- `task_goal`
- `user_state`
- `constraints`
- `hidden_tradeoff`
- `boundary_axes`
- `acceptable_diversity_notes`

### `eval-candidates/`

Stores prompt variants that are ready for calibration.

Required fields:

- `eval_id`
- `scenario_id`
- `task_family`
- `variant_type`
- `prompt`
- `expected_output`
- `judge_rubric`
- `must_preserve`
- `must_not_do`
- `expectations`

Allowed `variant_type` values:

- `base`
- `paraphrase`
- `info-missing`
- `boundary-stress`

### `calibration-reports/`

Stores the evidence that candidate evals are judge-stable and discriminative enough.

Required metadata fields:

- `report_id`
- `bundle_id`
- `package_name`
- `task_family`
- `calibrated_at`

Required per-eval fields:

- `eval_id`
- `scenario_id`
- `strong_vs_weak_win_rate`
- `judge_agreement_score`
- `tie_rate`
- `discriminative_score`
- `notes`

### `certified-evals/`

Stores only bundles that have passed the current thresholds.

Required metadata fields:

- `bundle_id`
- `package_name`
- `skill_name`
- `task_family`
- `certification_status`
- `calibration_report_path`

Required threshold fields:

- `strong_vs_weak_win_rate`
- `judge_agreement_score`
- `max_tie_rate`

Required per-eval fields:

- `eval_id`
- `scenario_id`
- `candidate_path`
- `variant_type`
- `certification_status`
- `discriminative_score`
- `judge_agreement_score`
- `tie_rate`
- `strong_vs_weak_win_rate`

## Certification Rules In V0.1

The current validation logic checks:

- the certified bundle exists and is marked `certified`
- every referenced scenario card exists
- every scenario card points to real source materials
- every referenced eval candidate exists and matches `eval_id`, `scenario_id`, and `variant_type`
- every eval clears the current thresholds
- the calibration report exists and matches the bundle metrics

Current thresholds:

- `strong_vs_weak_win_rate >= 0.70`
- `judge_agreement_score >= 0.75`
- `tie_rate < 0.60`

## First Certified Bundle

The first live bundle is:

- `eval-factory/certified-evals/swot-analysis/swot-analysis-certified-batch-v0.1.json`

It currently contains:

- `6` evals
- `3` scenario cards
- `3` source-bank records
- coverage for:
  - normal value-separation
  - information-insufficiency
  - boundary-stress

## Current Limitation

`v0.1` validates and exports certified bundles, but it does not run calibration automatically yet.

That keeps the first version small while still making the eval-factory auditable and ready to connect to package sync in the next step.

Mainline consumption is now package-driven:

- package declares its certified bundle upstream
- `prepare_iteration(...)` resolves evals through `toolchain.eval_factory.resolve_package_evals(...)`
- if `sync_on_read` is enabled, `evals/evals.json` is refreshed before the iteration scaffold is built

## Mainline Integration Status

`v0.1` mainline behavior is now locked to:

```text
certified-evals
  -> sync_package_evals(...)
  -> package evals/evals.json
  -> prepare_iteration(...)
  -> run_eval_pipeline
```

Operational rules:

- certified bundles are the default package eval source when `eval_source` is declared
- package-local `evals/evals.json` remains the fallback path
- Level 3 primary output is `differential-benchmark.json`
- Level 4-6 consume `level3-summary.json`, which normalizes differential and gate artifacts into a single handoff contract
