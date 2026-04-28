# Vision Skill 结构与功能说明

Last updated: 2026-04-26

本文用于帮助开发者和协作 agent 快速理解 `vision-skill` 的当前代码结构、主要功能点和新评测流程。

一句话概括：

```text
vision-skill 是一条本地优先的 skill 生产线：
package -> certified eval -> Kimi Code 执行 -> hard gate -> quantitative supporting bundle -> deep quality eval -> agent review report -> human authorization -> release recommendation
```

## 1. 当前主线

默认主链已经从“Level 1-6 逐层加权”收束为：

```text
certified eval sync
  -> prepare iteration
  -> package snapshot
  -> Kimi Code execution with_skill / without_skill
  -> hard-gate.json
  -> quantitative-summary.json
  -> deep-eval.json / deep-eval.md
  -> quality-failure-tags.json
  -> human-review-packet.md
  -> human-review-authorization.json
  -> release-recommendation.json
```

核心判断原则：

- `hard-gate.json` 只判断 artifacts 是否完整、是否能进入质量评测。
- `quantitative-summary.json` 是定量支持包，不是主质量结论。
- `deep-eval.json` 是机器侧主质量判断。
- `human-review-packet.md` 是给人类 reviewer 阅读的 LLM 可读报告。
- `human-review-authorization.json` 是当前主链的人工授权来源；没有明确授权，不得声称 release-ready。
- `benchmark.json`、`differential-benchmark.json`、`level3-summary.json`、`stability.json` 保留为兼容和诊断产物。

## 2. 仓库结构

```text
vision-skill/
  README.md
  docs/
  eval-factory/
  packages/
  package-workspaces/
  shared/
  toolchain/
  pyproject.toml
```

| 路径 | 作用 |
| --- | --- |
| `README.md` | 仓库入口、推荐命令和 release notes。 |
| `docs/` | 面向开发者和协作 agent 的稳定文档。 |
| `eval-factory/` | certified eval 的上游生产和登记区。 |
| `packages/` | 正式 skill package。 |
| `package-workspaces/` | 本地运行产物根目录，只提交 README。 |
| `shared/` | 共享索引、模板、taxonomy 和 review 资产。 |
| `toolchain/` | 执行、评测、深度评估、review、host adapter 和 Kimi worker 工具链。 |

## 3. Package 结构

标准 package：

```text
packages/<package>/
  SKILL.md
  evals/
    evals.json
    eval-sync.json
  metadata/
    package.json
    source-map.json
  references/
```

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | 轻量行为契约，描述触发、Step 0 路由、分支、输出骨架和反模式。 |
| `evals/evals.json` | package 当前消费的评测用例，可由 certified bundle 同步生成。 |
| `evals/eval-sync.json` | certified bundle 同步元数据。 |
| `metadata/package.json` | package 名称、版本、状态、eval source。 |
| `metadata/source-map.json` | demo/source 来源登记。 |
| `references/` | 长背景、长示例和方法说明；避免塞进 `SKILL.md` 主体。 |

当前 package：

- `swot-analysis`
- `golden-circle`
- `pyramid-principle`
- `mece-analysis`
- `first-principles`
- `five-whys`

进入 `packages/` 不等于已经 release-ready。发布质量必须由评测证据和人工 review 共同证明。

## 4. Iteration 结构

一次评测会生成：

```text
package-workspaces/<package>-workspace/
  latest-package/
    SKILL.md
    metadata/
    evals/
    manifest.json
  latest-skill.md
package-workspaces/
  upload-ready-skills/
    <package>/
      SKILL.md
    index.json
  <package>-workspace/
  iteration-N/
    package/
      SKILL.md
      metadata/
      evals/
      manifest.json
    eval-*/
      eval_metadata.json
      with_skill/
        run-1/
      without_skill/
        run-1/
    hard-gate.json
    quantitative-summary.json
    deep-eval.json
    deep-eval.md
    quality-failure-tags.json
    agent-review-report.json
    human-review-packet.md
    human-review-authorization.json
    release-recommendation.json
```

单个 run 的关键 artifacts：

```text
run-*/
  request.json
  raw_response.json
  transcript.json
  timing.json
  grading.json
  outputs/
    final_response.md
    latest_assistant_response.md
    turns/
      turn-1-assistant.md
      turn-2-assistant.md
```

含义：

- `iteration-N/package/`: 本轮评测真实使用的 package 快照，方便回看当轮 `SKILL.md`、metadata 和 evals。
- `latest-package/`: workspace 下的稳定入口，始终指向最近一次主链运行打包出的 package 快照。
- `latest-skill.md`: workspace 下最方便打开的最新 `SKILL.md` 副本。
- `upload-ready-skills/<package>/SKILL.md`: repo 级“纯 skill 上传版”目录，每个 package 只保留一个 `SKILL.md`。
- `upload-ready-skills/index.json`: 当前已导出的纯 skill 列表，便于快速查看有哪些模型可上传。
- `request.json`: 本次 run 的请求、配置、skill 使用方式、`execution_eval` 和 turn script。
- `raw_response.json`: Kimi workspace task 调用摘要、warnings、stderr、metadata。
- `transcript.json`: 标准化多轮对话和每轮 task 记录。
- `outputs/final_response.md`: 完整 user/assistant 对话拼接，默认作为完整体验证据。
- `outputs/latest_assistant_response.md`: 最后一轮 assistant 回答，供 deep eval 判断最终输出质量。
- `grading.json`: 规则型 expectation 检查结果，属于 supporting diagnostics。

## 5. Eval Source

Package 默认可从 certified bundle 同步 eval：

```json
{
  "eval_source": {
    "mode": "certified-bundle",
    "bundle_path": "../../eval-factory/certified-evals/<package>/<bundle>.json",
    "sync_on_read": true,
    "sync_output": "evals/evals.json"
  }
}
```

实现入口：

- `toolchain.eval_factory.sync.resolve_package_evals`

行为：

- 如果 package 声明 `certified-bundle`，主链先同步再读取。
- `evals/evals.json` 保留为可审阅的派生物。
- package 未声明 `eval_source` 时，读取本地 `evals/evals.json`。

## 6. 主链执行

默认入口：

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N>
```

默认入口是快速迭代 profile：

- `1` run per configuration。
- Pairwise judge 默认只跑 single-pass。
- 继续生成 `benchmark.json`、`differential-benchmark.json`、`level3-summary.json`、`stability.json`，但它们是 supporting diagnostics。

需要稳定性证据时再运行：

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --thorough
```

`--thorough` 会恢复慢速 profile：`3` runs per configuration + balanced pairwise judging。

快速 smoke：

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --smoke
```

执行器位置：

- `toolchain.executors.kimi_code_executor`

执行规则：

- `with_skill` 会把 `SKILL.md` 纳入受控任务上下文。
- `without_skill` 不提供 skill 正文，用于 baseline。
- Kimi 终端输出只作为日志。
- 正式结果必须来自 Kimi 写入的工作区文件。

## 7. Scripted Multi-Turn

主链现在支持单轮和固定脚本多轮。

Eval case 可选字段：

```json
{
  "execution_eval": {
    "enabled": true,
    "turn_script": [
      {"label": "initial", "text": "我想梳理一个新产品定位。"},
      {"label": "info-supply", "text": "目标用户是中小企业老板，预算有限。"},
      {"label": "continue", "text": "继续。"}
    ]
  }
}
```

优先级：

```text
execution_eval.turn_script
  -> legacy host_eval.turn_script fallback
  -> prompt
```

区别：

- `execution_eval.turn_script`: 主链执行脚本，用于 scripted API/Kimi lane。
- `host_eval.turn_script`: 真实宿主验证脚本，用于 host lane。

注意：

- 多轮执行不是等待真实用户输入，而是按 eval case 固定脚本推进。
- `outputs/final_response.md` 写完整对话。
- `outputs/latest_assistant_response.md` 写最后一轮 assistant 回答。

## 8. Kimi Workspace-File Task

当前主链不再要求 Kimi 在终端里返回大段 JSON 或完整文本。

统一模式：

```text
Codex prepares task workspace
  -> Kimi reads task.md / inputs / contracts
  -> Kimi writes outputs/
  -> Codex reads required output files
  -> terminal reply is debug log only
```

通用实现：

- `toolchain.kimi_runtime`: Kimi CLI 命令、环境变量、JSONL、session id、assistant text 解析。
- `toolchain.kimi_workspace`: 创建受控工作区任务，并强制读取 required output files。

典型工作区：

```text
task-workspace/
  task.md
  workspace-manifest.json
  inputs/
  contracts/
    output-contract.md
  outputs/
```

不同阶段的 required outputs：

| 阶段 | Kimi 写入 | Codex 读取用途 |
| --- | --- | --- |
| Executor turn | `outputs/assistant.md`, `outputs/run_metadata.json` | 形成 run responses 和 transcript。 |
| Pairwise judge | `outputs/judgment.json` | 生成 supporting differential diagnostics。 |
| Deep eval | `outputs/deep-eval.json` | 生成主质量判断。 |
| Kimi production worker | `outputs/eval-draft.json`, `outputs/SKILL.generated.md`, `outputs/run-report.json` | 供 Codex 校验、应用和重跑。 |

## 9. Hard Gate

模块：

- `toolchain.hard_gates`

产物：

- `hard-gate.json`

职责：

- 检查 run artifacts 是否存在。
- 检查 final/latest response 是否可读。
- 检查是否有足够证据进入 deep eval。
- 不判断 skill 内容好坏。

## 10. Quantitative Supporting Bundle

模块：

- `toolchain.quantitative`
- `toolchain.graders`
- `toolchain.judges`
- `toolchain.benchmarks`

产物：

- `quantitative-summary.json`
- `benchmark.json`
- `differential-benchmark.json`
- `level3-summary.json`
- `stability.json`

定位：

- 它们是 supporting diagnostics。
- 它们用于发现成本、稳定性、格式命中、pairwise 风险。
- 它们不再是 release 主判断。

## 11. Deep Quality Eval

模块：

- `toolchain.deep_evals`

产物：

- `deep-eval.json`
- `deep-eval.md`
- `quality-failure-tags.json`

输入：

- `outputs/final_response.md`
- `outputs/latest_assistant_response.md`
- `request.json`
- `transcript.json`
- `raw_response.json`
- `timing.json`
- `SKILL.md`
- 精简后的 eval/package packet

职责：

- 直接评价回答内容质量。
- 按保守 rubric 给出质量判断。
- 输出失败标签、修复层、代表性证据。
- 给 human review 提供可读判断。

Deep eval 不应直接消费完整 raw transcript 或超长 skill 文档；需要使用压缩 packet 和高价值 evidence snippets。

## 12. Human Review And Recommendation

模块：

- `toolchain.reviews`

产物：

- `human-review-packet.md`
- `agent-review-report.json`
- `human-review-authorization.json`
- `release-recommendation.json`

职责：

- 汇总 hard gate、deep eval、quantitative supporting evidence。
- 先生成结构化 `agent-review-report.json`，再由大模型渲染出可读的 `human-review-packet.md`。
- 通过对话确认把人工授权落盘到 `human-review-authorization.json`。
- 生成系统建议，但不替代人工结论。

最终 decision 只能由人工授权给出：

- `approve`
- `revise`
- `hold`

## 13. Host Lane

Host lane 用于验证真实 Kimi Code 宿主是否能触发并执行 skill 协议，不替代主链。

入口：

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --max-evals 4
```

流程：

```text
host_eval.enabled case
  -> KimiCodeHost
  -> host-transcript
  -> normalized events
  -> signal report
  -> protocol report
  -> trigger report
  -> host benchmark
```

主要产物：

- `host-session.json`
- `host-transcript.json`
- `host-normalized-events.json`
- `host-signal-report.json`
- `host-protocol-report.json`
- `host-trigger-report.json`
- `host-final-response.md`
- `host-grading.json`
- `host-benchmark.json`

使用时机：

- 主链 deep eval 已有正向证据。
- 需要验证真实宿主触发、读取顺序、多轮协议。
- release 前补真实环境证据。

## 14. Kimi Production Cycle

入口：

```bash
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --apply-generated-evals --apply-skill --run-eval
```

流程：

```text
Codex builds compact package packet
  -> Kimi reads workspace files
  -> Kimi writes generated evals / skill rewrite
  -> Codex validates output contract
  -> Codex applies accepted files
  -> Codex runs eval pipeline
  -> Codex decides next iteration
```

模块：

| 模块 | 作用 |
| --- | --- |
| `kimi_cycle/context.py` | 构造压缩 package packet、recent context、skill 摘要。 |
| `kimi_cycle/workspace_tasks.py` | 定义 Kimi worker 任务目录和输出契约。 |
| `kimi_cycle/eval_generation.py` | 让 Kimi 生成 eval draft。 |
| `kimi_cycle/skill_rewrite.py` | 让 Kimi 生成 skill rewrite draft。 |
| `kimi_cycle/kimi_cli.py` | Kimi CLI 兼容层，复用共享 runtime。 |
| `run_kimi_production_cycle.py` | 生产循环 CLI。 |

## 15. Toolchain 模块地图

| 模块 | 当前定位 |
| --- | --- |
| `eval_factory/` | certified eval sync 和 bundle 校验。 |
| `benchmarks/iteration_scaffold.py` | 创建 iteration/run 目录。 |
| `executors/` | Kimi Code 单轮/多轮执行。 |
| `hard_gates/` | artifacts 完整性和可评测性门禁。 |
| `quantitative/` | 定量支持包收口。 |
| `graders/` | 规则型 expectation 检查，supporting diagnostics。 |
| `judges/` | pairwise judge，supporting diagnostics。 |
| `benchmarks/` | legacy benchmark、differential、level3 summary、stability。 |
| `deep_evals/` | 当前主质量评测。 |
| `reviews/` | 人审 packet、score template、release recommendation。 |
| `agent_hosts/` | Kimi host validation。 |
| `kimi_cycle/` | Kimi worker 生产循环。 |
| `common.py` | JSON、文本、slug、eval id 等公共工具。 |
| `kimi_runtime.py` | Kimi CLI runtime 解析。 |
| `kimi_workspace.py` | 受控 workspace-file task。 |
| `run_eval_pipeline.py` | 默认主链入口。 |
| `run_level456.py` | 兼容/调试入口，不是日常推荐入口。 |

## 16. 新 Agent 阅读路径

另一个 Codex agent 接手时，建议按这个顺序：

1. 读 `README.md`，确认推荐命令。
2. 读 `docs/AGENT_SKILL_DEVELOPMENT_GUIDE.md`，复制执行提示词。
3. 读本文，理解模块边界。
4. 读 `toolchain/README.md`，确认 CLI 参数。
5. 读目标 package 的 `SKILL.md`、`metadata/package.json`、`evals/evals.json`。
6. 如果是优化任务，读最新 iteration 的 `deep-eval.json`、`quality-failure-tags.json`、`quantitative-summary.json`。

不要从旧 `analysis.json` 或 `level3-summary.json` 开始做质量判断。它们只适合兼容、定位或对照。

## 17. 完成标准

一次合格的开发/优化任务至少应说明：

- 修改了哪些文件。
- 运行了哪些验证命令。
- 生成或检查了哪些 artifacts。
- `hard-gate.json` 是否通过。
- `deep-eval.json` 暴露了什么质量结论。
- `quality-failure-tags.json` 中的主失败模式是否变化。
- `quantitative-summary.json` 是否出现明显退化。
- 是否需要 host lane 或 human review。

不要只凭“回答看起来更好”宣布完成。
