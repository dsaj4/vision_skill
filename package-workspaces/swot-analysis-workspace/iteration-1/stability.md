# Stability Report

**Generated At**: 2026-04-08T09:48:23Z

## Overall

- Runs per configuration: 1
- Flags: weak_stability_value

| Configuration | Pass Rate Mean | Pass Rate Stddev | Time Mean | Tokens Mean |
|---|---:|---:|---:|---:|
| with_skill | 0.8334 | 0.2357 | 50.53s | 3940 |
| without_skill | 0.8334 | 0.2357 | 46.77s | 2258 |

## Per Eval

### Eval 1: ai-swot
- Flags: none
- with_skill: pass mean 0.6667, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none

### Eval 2: 3-swot
- Flags: none
- with_skill: pass mean 1.0000, stddev 0.0000, drift=False, unstable_expectations=none
- without_skill: pass mean 0.6667, stddev 0.0000, drift=False, unstable_expectations=none
