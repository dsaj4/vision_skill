# Stability Report

**Generated At**: 2026-04-14T13:46:58Z

## Level 3

- Primary mode: differential
- Pairwise win rate: 0.0000
- Pairwise disagreement rate: 0.0000
- Cost-adjusted value: -0.7190

## Overall

- Runs per configuration: 1
- Flags: weak_stability_value

| Configuration | Pass Rate Mean | Pass Rate Stddev | Time Mean | Tokens Mean |
|---|---:|---:|---:|---:|
| with_skill | 1.0000 | 0.0000 | 42.98s | 3839 |
| without_skill | 0.8334 | 0.2357 | 66.32s | 3679 |

## Per Eval

### Eval 201: ai-1-2-3-10-4-mece
- Flags: weak_stability_value
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.6667, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.6250 disagreement=False

### Eval 202: mece
- Flags: weak_stability_value
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.8000 disagreement=False
