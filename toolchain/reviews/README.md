# Reviews

这里收口当前主链的 review / release 逻辑。

当前流程：

- 汇总 `hard-gate.json`、`deep-eval.json`、`quantitative-summary.json` 以及 supporting diagnostics
- 生成结构化 `agent-review-report.json`
- 让大模型把结构化报告渲染成可读的 `human-review-packet.md`
- 生成 `human-review-authorization.json` 模板，等待用户在对话里明确给出 `approve / revise / hold`
- 生成 `release-recommendation.json`

注意：

- `human-review-packet.md` 仍保留旧文件名，但内容已经升级为 LLM 可读审阅报告
- `human-review-authorization.json` 是当前主链的人审授权来源
- `human-review-score.json` 只保留为 legacy fallback，不再是新主链正式输入
