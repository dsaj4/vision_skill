# Executors

This module runs API-lane eval executions.

The executor reads `iteration-N/eval-*/with_skill|without_skill/run-*`, calls a model provider, and writes:

- `request.json`
- `raw_response.json`
- `transcript.json`
- `timing.json`
- `outputs/final_response.md`

## Provider Environment

The executor uses OpenAI-compatible Chat Completions. DashScope remains the default provider.

DashScope:

```powershell
$env:VISION_LLM_PROVIDER="dashscope"
$env:DASHSCOPE_API_KEY="<your-dashscope-key>"
```

Moonshot/Kimi API:

```powershell
$env:VISION_LLM_PROVIDER="moonshot"
$env:MOONSHOT_BASE_URL="https://api.moonshot.ai/v1"
$env:MOONSHOT_MODEL="kimi-k2.6"
$env:MOONSHOT_API_KEY="<your-moonshot-key>"
```

Kimi Code endpoint:

```powershell
$env:VISION_LLM_PROVIDER="kimi-code"
$env:KIMI_CODE_BASE_URL="https://api.kimi.com/coding/v1"
$env:KIMI_CODE_MODEL="kimi-for-coding"
$env:KIMI_CODE_API_KEY="<your-kimi-code-key>"
```

The executor appends `/chat/completions` when the configured base URL does not already include it.

## Kimi Code Limitation

Kimi Code is designed for coding agents such as Kimi CLI, Claude Code, Roo Code, and similar hosts. Its coding endpoint may reject generic scripted API calls even when the key is valid.

Use `VISION_LLM_PROVIDER=kimi-code` only when validating endpoint resolution or when Kimi enables generic direct calls for the account. For real Kimi Code skill behavior, use the host lane:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 4 --max-evals 4
```
