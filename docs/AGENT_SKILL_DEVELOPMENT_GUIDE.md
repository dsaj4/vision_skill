# Agent Skill Development Guide

Last updated: 2026-04-26

本指南面向在 `vision-skill` 仓库里继续开发 skill 的 Codex agent。它的目标是让新 agent 直接进入当前新评测流程，而不是回到旧的 demo 修改、Level 3 指标主导或终端回文模式。

## Copy-Paste Agent Prompt

把下面这段提示词交给另一个 Codex agent，即可让它按当前工程主线开始工作：

```text
你是一个在 `vision-skill` 仓库内工作的 Codex coding agent。

工作目录：
E:\Project\vision-lab\vision-skill

请用中文汇报过程和最终结果。Codex 是每一轮的总调控者；Kimi Code 可以作为执行、判分、深度评测或生产修改的 worker/host，但不能替代 Codex 做最终判断。

开始前先阅读这些文件：
1. README.md
2. docs/PROJECT.md
3. docs/STRUCTURE_AND_FUNCTIONS.md
4. docs/AGENT_SKILL_DEVELOPMENT_GUIDE.md
5. toolchain/README.md
6. packages/README.md

如果任务涉及某个具体 skill package，还要阅读：
1. packages/<package>/SKILL.md
2. packages/<package>/metadata/package.json
3. packages/<package>/metadata/source-map.json
4. packages/<package>/evals/evals.json
5. package-workspaces/<package>-workspace/README.md，如果存在

当前默认评测主链是：
certified eval sync
  -> prepare iteration
  -> Kimi Code execution with_skill / without_skill
  -> hard-gate.json
  -> quantitative-summary.json
  -> deep-eval.json / deep-eval.md
  -> quality-failure-tags.json
  -> human-review-packet.md
  -> human-review-authorization.json
  -> release-recommendation.json

当前质量判断规则：
- `hard-gate.json` 只判断 run artifacts 是否完整、能否进入质量评测。
- `quantitative-summary.json` 是定量支持包，用于诊断，不是主质量结论。
- `benchmark.json`、`differential-benchmark.json`、`level3-summary.json`、`stability.json` 是兼容和诊断产物。
- `deep-eval.json` 是机器侧主质量判断，直接消费原始回答和 run artifacts。
- `human-review-packet.md` 是给人类 reviewer 阅读的 LLM 可读报告，源数据在 `agent-review-report.json`。
- `human-review-authorization.json` 是最终人工授权来源；没有明确授权，不要声称 release-ready。

当前执行规则：
- 主链执行支持单轮和 scripted multi-turn。
- 优先使用 `execution_eval.turn_script` 作为主链多轮脚本。
- `host_eval.turn_script` 只属于真实宿主验证；主链 executor 仅保留旧数据兼容 fallback。
- `outputs/final_response.md` 保存完整 user/assistant 对话拼接。
- `outputs/latest_assistant_response.md` 保存最后一轮 assistant 回答。
- Kimi 终端回文只当日志；正式结果必须来自受控工作区文件。

如果任务是优化 skill，请按以下顺序做：
1. 找到目标 package 和最新 iteration。
2. 优先检查最新 iteration 下的：
   - hard-gate.json
   - deep-eval.json
   - deep-eval.md
   - quality-failure-tags.json
   - quantitative-summary.json
   - human-review-packet.md
   - release-recommendation.json
3. 只把旧的 benchmark/differential/level3/stability 当作 supporting diagnostics。
4. 提炼一个主失败模式和一个可验证的修补假设。
5. 每轮只做少数高影响修改，避免同时改 trigger、主体协议、示例和 eval。
6. 保持 `SKILL.md` 是轻量行为契约；长背景、长示例和方法材料放入 `references/`。
7. 修改后跑 validator 和同一批 eval，比较新旧 iteration 证据。

常用命令：

运行离线测试：
python -m pytest

运行 package/validator 相关测试：
python -m pytest toolchain/validators/tests

运行默认 Kimi Code 评测主链：
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N>

需要稳定性证据时再运行慢速 thorough profile：
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --thorough

运行快速 smoke：
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --smoke

运行 Kimi host 验证：
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --max-evals 4

运行 Codex 控制的 Kimi 生产循环：
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --apply-generated-evals --apply-skill --run-eval

重要约束：
- 不要提交 generated workspaces、transcripts、cache、exports、`.env` 或 API key。
- 不要只优化格式通过率；深度质量评测和人工 review 才是放行依据。
- 默认主链是快速迭代 profile：1 run/config + single-pass judge；不要在没有必要时直接跑 full/stability。
- 不要把 staged interaction 写成默认仪式；信息充分时优先直接给高质量结果。
- 不要让 Kimi 在终端返回大 JSON 或整份 SKILL；要让它读取工作区文件并写入指定 outputs。
- 不要未经验证就声称 skill 质量提升。
- 如果遇到旧 artifact，先识别它是 supporting diagnostic，避免把旧 Level 3 当主结论。

最终汇报请使用中文，并包含：
- 修改内容
- 验证命令
- 评测证据
- 结论
- 剩余风险
- 下一步建议
```

## Current Mental Model

当前项目把 skill 当作可迭代工程资产，而不是提示词片段：

```text
demo/source material
  -> package
  -> certified evals
  -> Kimi Code execution
  -> hard gate
  -> quantitative supporting bundle
  -> deep quality evaluation
  -> host validation when needed
  -> agent review report
  -> human authorization
  -> release artifact
```

关键变化是：深度质量评测现在是机器侧主判断，定量脚本被收束为 supporting bundle。旧的 `benchmark.json`、`differential-benchmark.json`、`level3-summary.json`、`stability.json` 仍然有诊断价值，但不再是“这个 skill 好不好”的主判据。

## First Files To Read

任何任务都先按需阅读，不要把整个仓库塞进上下文：

- `README.md`: 仓库级入口、推荐命令和当前 release notes。
- `docs/PROJECT.md`: 当前项目形态、主链和 release hygiene。
- `docs/STRUCTURE_AND_FUNCTIONS.md`: 代码结构和模块职责。
- `toolchain/README.md`: CLI、pipeline 和 advanced/internal 命令。
- `packages/README.md`: package contract。
- `packages/<package>/SKILL.md`: 当前 skill 行为契约。
- `packages/<package>/metadata/package.json`: package 身份和 eval source。
- `packages/<package>/evals/evals.json`: 当前 eval cases。

优化任务还要看最新 iteration artifacts：

- `package-workspaces/<package>-workspace/iteration-*/hard-gate.json`
- `package-workspaces/<package>-workspace/iteration-*/deep-eval.json`
- `package-workspaces/<package>-workspace/iteration-*/deep-eval.md`
- `package-workspaces/<package>-workspace/iteration-*/quality-failure-tags.json`
- `package-workspaces/<package>-workspace/iteration-*/quantitative-summary.json`
- `package-workspaces/<package>-workspace/iteration-*/agent-review-report.json`
- `package-workspaces/<package>-workspace/iteration-*/human-review-packet.md`
- `package-workspaces/<package>-workspace/iteration-*/human-review-authorization.json`
- `package-workspaces/<package>-workspace/iteration-*/release-recommendation.json`

## New Evaluation Flow

### 1. Certified Eval Sync

Package 可以通过 `metadata/package.json` 声明 certified eval bundle。主链会同步 bundle 到 `evals/evals.json`，让 package 侧保留一份可审阅派生物。

### 2. Prepare Iteration

`prepare_iteration` 会创建稳定的 `iteration-N` 目录，写入 eval metadata 和 with/without skill run 结构。

### 3. Kimi Code Execution

执行器使用受控 workspace-file task：

```text
task.md
  -> Kimi Code
  -> outputs/assistant.md
  -> outputs/run_metadata.json
```

如果 eval case 含 `execution_eval.turn_script`，执行器会按脚本多轮推进。每一轮都有自己的 task/run metadata，run 级 artifacts 会汇总成：

- `request.json`
- `transcript.json`
- `raw_response.json`
- `outputs/final_response.md`
- `outputs/latest_assistant_response.md`
- `outputs/turns/turn-N-assistant.md`

### 4. Hard Gate

`hard-gate.json` 只问一个问题：这些 artifacts 是否完整到足以评测。它不负责判断 skill 是否优秀。

### 5. Quantitative Supporting Bundle

`quantitative-summary.json` 统一收口旧定量结果，例如 pass rate、pairwise margin、stability flags。它用于帮助定位问题，不替代深度质量评测。

### 6. Deep Quality Eval

`deep-eval.json` / `deep-eval.md` 是主质量判断。它直接消费原始回答、latest assistant response、run artifacts 和精简 packet，按保守 rubric 评估内容质量。

### 7. Human Review And Release Recommendation

`human-review-packet.md` 是由大模型生成的人类可读审阅报告；`agent-review-report.json` 是对应的结构化镜像。人工不再手填评分表，而是通过对话明确给出 `approve / revise / hold`，由 agent 把结果落盘为 `human-review-authorization.json`。`release-recommendation.json` 只做系统建议，不覆盖人工授权。

## How To Optimize A Skill

推荐循环：

1. 读取最新 deep eval 和 failure tags。
2. 选择一个主失败模式。
3. 写一句修补假设，例如“rich input 默认 direct-result 后，最终回答质量应提高，staged friction 应下降”。
4. 只改能验证该假设的最小范围。
5. 运行 validator 和同一组 eval。
6. 比较新旧 iteration 的 deep eval、failure tags 和 quantitative summary。
7. 如果主失败模式仍在，不扩 eval，继续修补 skill 行为。

优先修改位置：

- Step 0 routing
- direct-result branch
- missing-info branch
- staged branch
- checkpoint rule
- output skeleton
- one or two examples
- anti-pattern list

避免一轮内混改：

- trigger description
- protocol shape
- eval set
- long reference material
- host lane

## Kimi Code Worker Pattern

Codex 控制生产循环，Kimi Code 执行受控文件任务：

```text
Codex writes compact workspace packet
  -> Kimi reads files
  -> Kimi writes required outputs
  -> Codex validates outputs
  -> Codex applies accepted changes
  -> Codex runs evals
```

Kimi 工作区通常包含：

- `task.md`
- `workspace-manifest.json`
- `inputs/package-packet.json`
- `inputs/recent-context.json`
- `inputs/current-skill.md`
- `inputs/examples.md`
- `contracts/output-contract.md`
- `examples/`

Kimi 终端回复应保持简短；正式内容必须写入约定文件。

## Host Lane

Host lane 用于验证真实宿主能否触发 skill、是否按协议走多轮。它不是日常优化的第一入口。

使用时机：

- API/Kimi mainline 已有正向证据。
- 需要验证真实宿主触发、读取顺序、多轮协议。
- 准备 release 前补真实环境证据。

Host lane 使用 `host_eval.turn_script`，不要和主链 `execution_eval.turn_script` 混淆。

## What Counts As Progress

有效进展：

- validator 通过。
- `hard-gate.json` 显示 artifacts 可评测。
- `deep-eval.json` 的主问题减少或质量分提高。
- `quality-failure-tags.json` 中的旧主失败模式消失或减弱。
- `quantitative-summary.json` 没有暴露明显成本、稳定性或 pairwise 退化。
- 人审 packet 能让人快速判断是否 pass/revise/hold。

无效进展：

- `SKILL.md` 看起来更漂亮，但没有评测证据。
- 格式命中率提高，但深度质量更差。
- prompt 变长、成本变高，却没有质量收益。
- staged protocol 像仪式，不像对用户有帮助。
- 没有人审就宣称 release-ready。

## Agent Report Template

新 agent 结束任务时，用中文汇报：

```text
修改内容：
- <文件或模块>

验证命令：
- <实际运行的命令>

评测证据：
- <检查或生成的 artifacts>
- <关键指标或质量变化>

结论：
- <continue / revise / hold / ready for human review>

剩余风险：
- <仍不确定的地方>

下一步：
- <一个最推荐的后续动作>
```
