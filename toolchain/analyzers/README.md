# Analyzers

This module contains Level 5 mechanism analysis.

Current behavior:

- reads `level3-summary.json`, `benchmark.json`, `stability.json`, run artifacts, and `SKILL.md`
- builds a bounded analyzer packet
- runs the analyzer through a controlled Kimi workspace-file task by default
- writes `analysis.json`, `analysis.md`, and `failure-tags.json`

The analyzer no longer calls direct model-provider endpoints. Use `--analyzer-model` or `KIMI_CLI_MODEL` when a Kimi model override is needed.

The analyzer result is read from `.kimi-analysis/outputs/analysis.json`. Kimi terminal text is retained only as debug log and is not parsed as the source of truth.
