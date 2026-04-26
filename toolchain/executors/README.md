# Executors

This module runs the Kimi Code eval mainline.

The executor reads `iteration-N/eval-*/with_skill|without_skill/run-*`, runs Kimi through the local Kimi CLI, and writes the same artifact contract used by the benchmark stack:

- `request.json`
- `raw_response.json`
- `transcript.json`
- `timing.json`
- `outputs/final_response.md`

## Runtime

The main executor is:

- `kimi_code_executor.py`

Execution mode:

- `with_skill`: creates a controlled workspace-file task for each scripted turn, installs a workspace-local `.kimi/skills/<package>/SKILL.md` proxy, and lets Kimi Code read the canonical package skill.
- `without_skill`: creates the same controlled workspace-file task without installing the skill proxy.

The terminal response is treated as debug log only. The source of truth is always the required workspace output file, then copied into the normal run artifact:

```text
iteration-N/.kimi-sessions/e<id>-<configuration>-run-<n>/turn-<m>/
  task.md
  workspace-manifest.json
  inputs/conversation.json
  contracts/output-contract.md
  outputs/assistant.md
  outputs/run_metadata.json
```

`outputs/assistant.md` is copied to `run-*/outputs/final_response.md` for grading and benchmarking.

## Environment

Kimi CLI must be installed and logged in.

Optional model override:

```powershell
$env:KIMI_CLI_MODEL="kimi-for-coding"
```

If `KIMI_CLI_MODEL` is not set, the executor lets Kimi CLI use its own configured default model.

## Notes

- Token counts from Kimi CLI are currently unavailable, so `timing.json` writes token fields as `0` with `token_source = kimi-cli-unavailable`.
- The executor intentionally does not call direct Chat Completions endpoints.
- The executor intentionally does not parse the final answer from Kimi terminal text.
- Long Windows paths are avoided by storing Kimi session directories under `iteration-N/.kimi-sessions/`.
