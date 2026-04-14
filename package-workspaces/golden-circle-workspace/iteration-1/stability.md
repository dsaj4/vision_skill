# Stability Report

**Generated At**: 2026-04-14T14:09:36Z

## Level 3

- Primary mode: differential
- Pairwise win rate: 0.0000
- Pairwise disagreement rate: 0.0000
- Cost-adjusted value: -0.6299

## Overall

- Runs per configuration: 1
- Flags: weak_stability_value

| Configuration | Pass Rate Mean | Pass Rate Stddev | Time Mean | Tokens Mean |
|---|---:|---:|---:|---:|
| with_skill | 0.8333 | 0.2887 | 64.33s | 4314 |
| without_skill | 0.8333 | 0.2887 | 70.18s | 2717 |

## Per Eval

### Eval 151: 1-2-3-6-20-4
- Flags: weak_stability_value
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.4250 disagreement=False

### Eval 152: eval
- Flags: weak_stability_value
- with_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.6500 disagreement=False

### Eval 153: why-how
- Flags: weak_stability_value
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.5500 disagreement=False
