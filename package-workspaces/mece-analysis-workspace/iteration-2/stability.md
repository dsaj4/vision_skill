# Stability Report

**Generated At**: 2026-04-14T14:17:50Z

## Level 3

- Primary mode: differential
- Pairwise win rate: 0.0000
- Pairwise disagreement rate: 0.0000
- Cost-adjusted value: -0.7250

## Overall

- Runs per configuration: 1
- Flags: weak_stability_value

| Configuration | Pass Rate Mean | Pass Rate Stddev | Time Mean | Tokens Mean |
|---|---:|---:|---:|---:|
| with_skill | 1.0000 | 0.0000 | 37.53s | 3430 |
| without_skill | 0.4444 | 0.5092 | 69.41s | 3516 |

## Per Eval

### Eval 201: ai-1-2-3-10-4-mece
- Flags: weak_stability_value
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.3333, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.6500 disagreement=False

### Eval 202: mece
- Flags: weak_stability_value
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.7250 disagreement=False

### Eval 203: mece
- Flags: weak_stability_value
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.0000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.8000 disagreement=False
