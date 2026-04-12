# Executors

这里放真实执行 run 的执行器。

第一版目标：
- 读取 `iteration-N/eval-*/with_skill|without_skill/run-*`
- 调用真实模型 provider
- 在 run 目录写入：
  - `request.json`
  - `raw_response.json`
  - `transcript.json`
  - `timing.json`
  - `outputs/final_response.md`

当前第一版 executor 使用 DashScope OpenAI-compatible Chat Completions 接口。
