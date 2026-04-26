# Judges

This module contains the new differential-evaluation core for Level 3B.

Current modules:

- `pairwise_judge.py`
  - blind A/B comparison for `with_skill` vs `without_skill`
  - default Kimi judging runs as a workspace-file task and reads `outputs/judgment.json`
- `consensus.py`
  - reconcile forward and reversed judgments into one pair-level result

These modules are designed to run in parallel with the old rule-based benchmark path during migration.

Kimi terminal text is debug log only. The judge never treats terminal prose as the canonical pairwise result.
