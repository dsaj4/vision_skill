# Stability Report

**Generated At**: 2026-04-14T14:16:39Z

## Level 3

- Primary mode: differential
- Pairwise win rate: 0.0000
- Pairwise disagreement rate: 0.0000
- Cost-adjusted value: -0.6286

## Overall

- Runs per configuration: 1
- Flags: instability_risk, weak_stability_value

| Configuration | Pass Rate Mean | Pass Rate Stddev | Time Mean | Tokens Mean |
|---|---:|---:|---:|---:|
| with_skill | 0.6667 | 0.2887 | 37.16s | 3599 |
| without_skill | 0.4444 | 0.0962 | 45.97s | 2451 |

## Per Eval

### Eval 161: 1-2-ramp-up-3-4-ceo-10
- Flags: weak_stability_value
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.3333, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.4250 disagreement=False

### Eval 162: eval
- Flags: weak_stability_value
- with_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.5000 disagreement=False

### Eval 163: eval
- Flags: weak_stability_value
- with_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.7500 disagreement=False
