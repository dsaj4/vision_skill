# Eval Factory

`eval-factory/` is the file-based upstream for certified evaluation assets.

Flow:

```text
source-bank
  -> scenario-cards
  -> eval-candidates
  -> calibration-reports
  -> certified-evals
```

This directory is intentionally lightweight in `v0.1`.

## Current Package Coverage

- `swot-analysis`
  - first certified batch: `6` evals
  - includes normal, info-missing, and boundary-stress coverage

## Directory Contract

- `source-bank/`
  - raw materials such as demo prompts, historical failures, and boundary-sensitive seeds
- `scenario-cards/`
  - reusable task abstractions derived from source materials
- `eval-candidates/`
  - prompt variants ready for calibration
- `calibration-reports/`
  - evidence that a candidate set is discriminative and judge-stable enough
- `certified-evals/`
  - only bundles that passed the current certification thresholds

## Current Thresholds

- `strong_vs_weak_win_rate >= 0.70`
- `judge_agreement_score >= 0.75`
- `tie_rate < 0.60`

## Consumption

The current mainline now supports certified-bundle consumption by default when a package declares:

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

The current bridge supports:

1. validate a certified bundle with `toolchain.eval_factory`
2. export it into package-style `evals.json`
3. sync that output into a package automatically on read
4. preserve optional `host_eval` blocks when a candidate needs real-host validation
