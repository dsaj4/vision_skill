# Stability Report

**Generated At**: 2026-04-14T11:00:00Z

## Level 3

- Primary mode: differential
- Pairwise win rate: 0.5000
- Pairwise disagreement rate: 0.0000
- Cost-adjusted value: -0.2547

## Overall

- Runs per configuration: 3
- Flags: drift_detected, unstable, weak_stability_value

| Configuration | Pass Rate Mean | Pass Rate Stddev | Time Mean | Tokens Mean |
|---|---:|---:|---:|---:|
| with_skill | 0.7315 | 0.3322 | 31.87s | 2707 |
| without_skill | 0.6945 | 0.2243 | 27.62s | 1070 |

## Per Eval

### Eval 101: ai-swot
- Flags: drift_detected, unstable, weak_stability_value
- with_skill: pass mean 0.8889, stddev 0.1924, drift=True, unstable_expectations=['strategy-guidance']
- without_skill: pass mean 1.0000, stddev 0.0000, drift=True, unstable_expectations=none
- pairwise: winner=without_skill margin=0.8500 disagreement=False

### Eval 102: ai-swot
- Flags: drift_detected, weak_stability_value
- with_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.5000, stddev 0.0000, drift=True, unstable_expectations=none
- pairwise: winner=without_skill margin=0.6500 disagreement=False

### Eval 103: 3-swot
- Flags: unstable
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.8889, stddev 0.1924, drift=False, unstable_expectations=['strategy-guidance']
- pairwise: winner=with_skill margin=0.7200 disagreement=False

### Eval 104: swot
- Flags: unstable
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.7778, stddev 0.1924, drift=False, unstable_expectations=['strategy-guidance']
- pairwise: winner=with_skill margin=0.7700 disagreement=False

### Eval 105: swot
- Flags: drift_detected, unstable, weak_stability_value
- with_skill: pass mean 0.1667, stddev 0.2887, drift=True, unstable_expectations=['boundary-slow-down']
- without_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=without_skill margin=0.8500 disagreement=False

### Eval 106: eval
- Flags: drift_detected, unstable
- with_skill: pass mean 0.8333, stddev 0.2887, drift=True, unstable_expectations=['de-escalation-signal']
- without_skill: pass mean 0.5000, stddev 0.0000, drift=False, unstable_expectations=none
- pairwise: winner=with_skill margin=0.5000 disagreement=False
