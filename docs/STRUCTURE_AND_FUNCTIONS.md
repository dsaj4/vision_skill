# Vision Skill 结构与功能说明

Last updated: 2026-04-25

本文用于帮助开发者和协作 agent 快速理解 `vision-skill` 当前的项目结构、功能模块和整体工作流。

一句话概括：

```text
vision-skill 不是 skill demo 仓库，而是一条本地优先的 skill 生产线。
它把 skill 从 package、评测集、Kimi Code 执行、差分评测、机制分析、真实宿主验证，一直推进到人工审核和待发布产物。
```

## 1. 总体目标

项目当前要解决的问题是：

- 让 Vision skill 不再靠手工改 prompt 和主观感觉判断质量。
- 让每个 skill 都有标准 package、标准 eval、标准执行产物和可复查报告。
- 用 Kimi Code 跑真实执行和差分评测，但由 Codex 负责总控、验收和迭代决策。
- 用文件化产物记录每一轮失败、修复和下一轮方向。

当前主线是：

```text
demo-origin package
  -> certified evals
  -> Kimi Code workspace-file execution
  -> hard gate
  -> quantitative supporting bundle
  -> deep quality eval
  -> Kimi host validation
  -> human review
  -> release recommendation
```

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
| `README.md` | 仓库入口，说明当前范围、快速命令和 release notes。 |
| `docs/` | 面向开发者和协作 agent 的项目文档。 |
| `eval-factory/` | certified eval 的上游生产和登记区。 |
| `packages/` | 正式 skill package 目录，每个 package 都有 `SKILL.md`、metadata 和 evals。 |
| `package-workspaces/` | 本地运行产物目录，只提交 README，不提交真实运行结果。 |
| `shared/` | 共享索引、审核模板、失败 taxonomy 等公共材料。 |
| `toolchain/` | 评测、执行、分析、审核和 Kimi 生产线代码。 |
| `pyproject.toml` | Python 包配置和测试配置。 |

## 3. 当前核心对象

| 对象 | 位置 | 含义 |
| --- | --- | --- |
| Skill package | `packages/<package>/` | 一个可评测、可迭代、可发布的 skill 单元。 |
| Skill 主体 | `packages/<package>/SKILL.md` | skill 的正式行为契约。 |
| Package metadata | `packages/<package>/metadata/package.json` | package 身份、状态、版本、eval 来源声明。 |
| Source map | `packages/<package>/metadata/source-map.json` | skill 与 demo/source 的来源关系。 |
| Package evals | `packages/<package>/evals/evals.json` | package 当前消费的评测集，可以由 certified bundle 同步生成。 |
| Certified bundle | `eval-factory/certified-evals/.../*.json` | 经过校准的评测包，是 package eval 的上游可信来源。 |
| Iteration | `package-workspaces/<package>-workspace/iteration-N/` | 一轮评测和分析的证据容器。 |
| Run artifact | `iteration-N/eval-*/with_skill|without_skill/run-*` | 单次执行结果、请求、响应、计时和评分。 |
| Hard gate | `iteration-N/hard-gate.json` | 判断 run artifacts 是否完整、是否可进入质量评测。 |
| Quantitative summary | `iteration-N/quantitative-summary.json` | 汇总旧定量指标，作为 supporting evidence。 |
| Deep eval | `iteration-N/deep-eval.json` | 当前主质量判断产物，直接消费原始回答和 run artifacts。 |
| Level 3 summary | `iteration-N/level3-summary.json` | 兼容旧差分主线的 supporting artifact。 |
| Review packet | `iteration-N/human-review-packet.md` | 给人工审核看的证据包。 |

## 4. 当前 packages

当前仓库内的正式候选包：

| Package | 状态说明 |
| --- | --- |
| `swot-analysis` | 当前 reference package，完整主链优先围绕它验证。 |
| `golden-circle` | 思维模型候选包，已进入标准 package 结构。 |
| `pyramid-principle` | 思维模型候选包，已进入标准 package 结构。 |
| `mece-analysis` | 思维模型候选包，已进入标准 package 结构。 |
| `first-principles` | 思维模型候选包，已进入标准 package 结构。 |
| `five-whys` | 思维模型候选包，已进入标准 package 结构。 |

注意：进入 `packages/` 不等于已经达到发布质量。发布质量必须由评测、稳定性、机制分析、真实宿主验证和人工审核共同证明。

## 5. Package 内部结构

标准 package 结构：

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

| 文件或目录 | 作用 |
| --- | --- |
| `SKILL.md` | 轻量核心行为契约，描述触发、Step 0 路由、分支、输出骨架和反模式。 |
| `evals/evals.json` | 当前评测用例。主链默认读取这里。 |
| `evals/eval-sync.json` | 记录 certified bundle 同步来源和稳定元数据。 |
| `metadata/package.json` | package 名称、skill 名称、版本、状态、eval source。 |
| `metadata/source-map.json` | demo/source 来源登记。 |
| `references/` | 长背景、长示例、说明材料。主体 `SKILL.md` 应尽量短。 |

## 6. Eval Factory 功能

`eval-factory/` 用于把原始材料加工成可认证、可复用的评测集。

```text
source-bank
  -> scenario-cards
  -> eval-candidates
  -> calibration-reports
  -> certified-evals
```

| 阶段 | 作用 |
| --- | --- |
| `source-bank/` | 存放 demo prompt、历史失败、边界样本等原始材料。 |
| `scenario-cards/` | 把原始材料抽象成可复用场景。 |
| `eval-candidates/` | 生成具体评测 prompt 和 expectation。 |
| `calibration-reports/` | 记录候选 eval 是否有区分度、judge 是否稳定。 |
| `certified-evals/` | 通过阈值的正式评测 bundle。 |

当前 package 通过 `metadata/package.json` 里的 `eval_source` 声明消费 certified bundle：

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

主链读取 package eval 时，如果声明了 `certified-bundle`，会先同步 bundle，再读取派生出的 `evals/evals.json`。

## 7. Toolchain 功能总览

`toolchain/` 是项目的执行核心。

| 模块 | Level | 主要功能 |
| --- | --- | --- |
| `validators/` | Level 1-2 | 检查 package 结构、metadata、evals 和 skill 协议。 |
| `eval_factory/` | 上游准备 | 校验 certified bundle，并同步到 package evals。 |
| `benchmarks/iteration_scaffold.py` | 准备阶段 | 根据 evals 创建 `iteration-N/eval-*` 运行目录。 |
| `executors/` | Level 3 执行 | 用 Kimi Code 跑 `with_skill / without_skill`。 |
| `graders/` | Level 3A | 对单次回答做规则型 gate grading。 |
| `judges/` | Level 3B | 对 `with_skill` 和 `without_skill` 做盲测差分判分。 |
| `benchmarks/` | Level 3-4 | 聚合 gate benchmark、differential benchmark、stability。 |
| `analyzers/` | Level 5 | 分析为什么 skill 赢或输，输出 failure tags 和 repair layer。 |
| `reviews/` | Level 6 | 生成人人审 packet、score template 和 release recommendation。 |
| `agent_hosts/` | Host lane | 用真实 Kimi Code host 验证 trigger 和多轮协议。 |
| `kimi_cycle/` | 生产循环 | 让 Kimi 作为受控 worker 生成 eval draft 和 skill rewrite。 |
| `common.py` | 公共工具 | JSON、文本、slug、eval id、文本压缩等工具。 |
| `kimi_runtime.py` | Kimi CLI 基础层 | 解析 Kimi 命令、环境变量、JSONL、session id。 |
| `kimi_workspace.py` | Kimi 文件任务层 | 创建受控 workspace task，并强制读取输出文件作为结果。 |
| `run_eval_pipeline.py` | 主入口 | 串起 eval 同步、执行、benchmark、Level 4-6。 |
| `run_kimi_production_cycle.py` | 生产入口 | 串起 Kimi 生成 eval、重写 skill、应用、重跑评测。 |
| `run_level456.py` | 分段入口 | 单独跑 stability、analysis、review。 |

## 8. Kimi Code 受控工作区文件任务

当前主链不再要求 Kimi 在终端里返回大段 JSON 或完整回答。

统一原则：

```text
Codex 准备 task workspace
  -> Kimi 读取 task.md、inputs、contracts
  -> Kimi 写 outputs/
  -> Codex 读取 outputs 并校验
  -> 终端输出只作为 debug log
```

核心实现是 `toolchain/kimi_workspace.py`。

标准任务目录：

```text
task-workspace/
  task.md
  workspace-manifest.json
  inputs/
  contracts/
    output-contract.md
  outputs/
```

当前主链的三个关键输出源：

| 阶段 | Kimi 必须写入 | Codex 读取用途 |
| --- | --- | --- |
| 执行器 | `outputs/assistant.md` | 复制为 `run-*/outputs/final_response.md`，进入 grader 和 benchmark。 |
| Pairwise judge | `outputs/judgment.json` | 生成 pairwise judgment 和 differential benchmark。 |
| Mechanism analyzer | `outputs/analysis.json` | 生成 `analysis.json`、`analysis.md` 和 failure tags。 |

这个设计的好处：

- 结果可复查，不依赖终端最后一句话。
- JSON 不容易被 markdown 包裹或污染。
- 大上下文可以拆成多个文件给 Kimi 读取。
- Codex 可以用 required output files 做硬校验。

## 9. 主评测链路

默认命令：

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --runs-per-configuration 3
```

完整流程：

```text
1. resolve package evals
2. prepare iteration
3. execute with_skill and without_skill, including scripted multi-turn when `execution_eval.turn_script` is present
4. run hard gate
5. run quantitative supporting bundle
6. run deep quality eval
7. generate human review packet
8. generate release recommendation
```

### 9.1 Eval 解析与同步

入口：`toolchain.eval_factory.sync.resolve_package_evals`

功能：

- 读取 package 的 `metadata/package.json`。
- 如果 `eval_source.mode = certified-bundle`，先读取上游 bundle。
- 把 certified bundle 导出成 package 风格的 `evals/evals.json`。
- 保留 `execution_eval`、`host_eval` 等扩展字段。

主要产物：

- `packages/<package>/evals/evals.json`
- `packages/<package>/evals/eval-sync.json`

Eval script fields:

- `execution_eval.turn_script` is the main evaluation-lane multi-turn script. It drives `execute_iteration`.
- `host_eval.turn_script` is reserved for real host validation. The executor keeps a temporary fallback to it for legacy evals only.

### 9.2 Iteration 准备

入口：`toolchain.benchmarks.iteration_scaffold.prepare_iteration`

功能：

- 为每个 eval 创建运行目录。
- 为每个 eval 创建 `with_skill` 和 `without_skill` 两个配置。
- 按 `runs_per_configuration` 创建 `run-1..run-N`。
- 写入 `eval_metadata.json`，供后续执行器读取。

典型目录：

```text
iteration-1/
  eval-101-scenario/
    eval_metadata.json
    with_skill/
      run-1/
    without_skill/
      run-1/
```

### 9.3 Kimi Code 执行

入口：`toolchain.executors.kimi_code_executor.execute_iteration`

功能：

- 读取每个 run 的 eval metadata。
- 对 `with_skill` 创建 skill proxy，让 Kimi 读取 package 内的 canonical `SKILL.md`。
- 对 `without_skill` 不安装 skill proxy，作为 baseline。
- 每个用户 turn 都创建受控工作区文件任务。
- 要求 Kimi 写 `outputs/assistant.md` 和 `outputs/run_metadata.json`。
- 把完整多轮对话写成标准产物 `run-*/outputs/final_response.md`。
- 把最后一轮 assistant 回答单独写入 `run-*/outputs/latest_assistant_response.md`。

Current multi-turn contract:

- Turn source precedence: `execution_eval.turn_script` -> legacy `host_eval.turn_script` fallback -> single `prompt`.
- Each scripted turn is executed as a controlled Kimi workspace-file task with full conversation history.
- `outputs/final_response.md` contains the full user/assistant conversation transcript for the run.
- `outputs/latest_assistant_response.md` contains only the last assistant answer.
- `outputs/turns/turn-N-assistant.md` stores each assistant turn separately for debugging.

单次 run 产物：

```text
run-1/
  request.json
  raw_response.json
  transcript.json
  timing.json
  outputs/
    final_response.md
    latest_assistant_response.md
    turns/
      turn-1-assistant.md
```

内部 Kimi 任务产物：

```text
iteration-1/.kimi-sessions/e101-with_skill-run-1/turn-1/
  task.md
  workspace-manifest.json
  inputs/conversation.json
  contracts/output-contract.md
  outputs/assistant.md
  outputs/run_metadata.json
```

### 9.4 Gate Grading

入口：`toolchain.graders.capability_grader.grade_response_text`

功能：

- 对单个回答执行规则型 expectation 检查。
- 检查 contains、contains_all、not_contains、结构信号等基础条件。
- 生成每个 run 的 `grading.json`。

定位：

- 它不是最终价值判断。
- 它负责发现空回答、格式明显不合规、基础 expectation 未命中等问题。

### 9.5 Supporting Benchmark

入口：`toolchain.benchmarks.run_benchmark`

功能：

- 聚合所有 `grading.json`。
- 输出 pass rate、tokens、time、errors 等支持性指标。

主要产物：

- `benchmark.json`
- `benchmark.md`

定位：

- `benchmark.json` 是 gate/supporting artifact。
- 它不再是 Level 3 的主价值判断。

### 9.6 Differential Benchmark

入口：`toolchain.benchmarks.run_differential_benchmark`

功能：

- 收集同一 eval、同一 run number 下的 `with_skill` 和 `without_skill`。
- 用 pairwise judge 做盲测比较。
- 分 forward 和 reversed 两个方向，必要时做 tiebreak。
- 通过 consensus 生成最终 pairwise 结果。

Pairwise judge：

- 位于 `toolchain.judges.pairwise_judge`。
- 默认通过 Kimi workspace-file task 执行。
- Kimi 必须写 `outputs/judgment.json`。

主要产物：

- `pairwise-judgment.json`
- `pairwise-judgment-reversed.json`
- `pairwise-consensus.json`
- `differential-benchmark.json`
- `differential-benchmark.md`

定位：

- `differential-benchmark.json` 是 Level 3 主价值信号。
- 核心指标包括 win rate、tie rate、avg margin、judge disagreement、cost-adjusted value。

### 9.7 Level 3 Summary

入口：`toolchain.benchmarks.level3_summary.ensure_level3_summary`

功能：

- 把 differential benchmark 和 supporting benchmark 归一化。
- 为 Level 4-6 提供唯一主读取入口。

主要产物：

- `level3-summary.json`

固定含义：

- `primary_mode = differential`
- `primary_artifact_path` 指向 differential benchmark
- `gate_summary` 保留旧 gate 指标
- `pairwise_summary` 保留差分核心指标
- `per_eval` 保留每个 eval 的 pairwise 结果和 run 路径

## 10. Level 4-6 深度评测

> Current implementation note: the default pipeline has been refactored. Old Level 4-6 artifacts are now compatibility/supporting diagnostics. The quality mainline is `hard-gate.json -> quantitative-summary.json -> deep-eval.json -> human-review-packet.md -> release-recommendation.json`.

New primary artifacts:
- `hard-gate.json`: checks whether run artifacts are complete enough to evaluate.
- `quantitative-summary.json`: packages old benchmark, differential, Level 3, and stability signals as supporting evidence.
- `deep-eval.json`: primary quality judgment based on raw model answers and run artifacts.
- `quality-failure-tags.json`: quality-layer failure tags and repair layers.

Level 4-6 不重新执行模型，而是消费已有 artifacts。

```text
level3-summary + benchmark + run artifacts
  -> stability
  -> mechanism analysis
  -> human review packet
  -> release recommendation
```

### 10.1 Level 4 Stability

入口：`toolchain.benchmarks.stability.generate_stability_report`

回答的问题：

```text
这个 skill 稳不稳定？
```

功能：

- 比较多次 run 的波动。
- 统计 pass rate、time、tokens 的均值和方差。
- 统计 expectation 级别的通过波动。
- 检查结构漂移信号。
- 结合 differential 指标判断 weak stability value、instability risk 等风险。

主要产物：

- `stability.json`
- `stability.md`
- `variance-by-expectation.json`

### 10.2 Level 5 Mechanism Analysis

入口：`toolchain.analyzers.mechanism_analyzer.analyze_iteration`

回答的问题：

```text
它为什么好，或者为什么坏？
```

功能：

- 读取 `level3-summary.json`、`benchmark.json`、`stability.json`、run artifacts 和 `SKILL.md`。
- 构造 bounded analysis packet。
- 通过 Kimi workspace-file task 要求写 `outputs/analysis.json`。
- 把失败归因到 `source`、`blueprint-spec`、`template`、`skill-content`。

主要产物：

- `analysis.json`
- `analysis.md`
- `failure-tags.json`

定位：

- 它不是给 release 自动拍板。
- 它负责解释失败模式，指导下一轮 skill 优化。

### 10.3 Level 6 Cognitive Review

入口：`toolchain.reviews.cognitive_review`

回答的问题：

```text
这个 skill 是否真的符合 VisionTree，是否值得放行？
```

功能：

- 汇总 benchmark、stability、analysis。
- 选择代表性 run。
- 生成给人工 reviewer 的 review packet。
- 生成可填写的 score template。
- 基于当前证据生成 release recommendation。

主要产物：

- `human-review-packet.md`
- `human-review-score.json`
- `release-recommendation.json`

注意：

- Level 6 不自动放行。
- 最终 `pass / revise / hold` 应由人工审核决定。

## 11. Kimi Host Validation

Host lane 用来验证真实宿主里的 skill 行为，不替代主评测链。

入口：

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --max-evals 4
```

回答的问题：

```text
真实 Kimi Code 宿主会不会触发 skill？
触发后多轮协议是否真的执行？
宿主噪音、读取顺序、协议漂移是否会影响结果？
```

流程：

```text
host-enabled eval case
  -> KimiCodeHost
  -> host-transcript
  -> normalized events
  -> signal report
  -> protocol report
  -> trigger report
  -> host grading
  -> host benchmark
```

主要模块：

| 模块 | 作用 |
| --- | --- |
| `kimi_code_host.py` | 创建 Kimi skill proxy，调用真实 Kimi CLI host。 |
| `event_normalizer.py` | 把 raw transcript 变成统一事件。 |
| `signal_extractor.py` | 提取 trigger、routing、protocol、结构和 host interference 信号。 |
| `protocol_classifier.py` | 用状态机判断 observed protocol path。 |
| `host_benchmark.py` | 聚合 host 指标。 |
| `run_host_eval.py` | Host lane CLI 入口。 |

Host lane 产物：

- `host-session.json`
- `host-transcript.json`
- `host-normalized-events.json`
- `host-signal-report.json`
- `host-protocol-report.json`
- `host-trigger-report.json`
- `host-final-response.md`
- `host-grading.json`
- `host-benchmark.json`

第一版重点指标：

- `trigger_success_rate`
- `false_trigger_rate`
- `skill_read_before_first_answer_rate`
- `canonical_skill_read_rate`
- `protocol_path_match_rate`
- `direct_result_compliance_rate`
- `followup_precision`
- `checkpoint_obedience_rate`
- `premature_full_answer_rate`
- `branch_recovery_rate`

## 12. Kimi Production Cycle

生产循环用于让 Kimi Code 作为 worker 帮忙生成 eval draft 和 skill rewrite，但 Codex 仍然是总控。

入口：

```bash
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --apply-generated-evals --apply-skill --run-eval
```

流程：

```text
Codex 收集 package packet、recent context、当前 SKILL、examples
  -> Codex 写入受控 workspace task
  -> Kimi 读取文件并写 outputs
  -> Codex 校验输出格式和 package contract
  -> Codex 决定是否 apply
  -> Codex 触发下一轮 eval
```

主要模块：

| 模块 | 作用 |
| --- | --- |
| `kimi_cycle/context.py` | 构造压缩后的 package packet、recent context、skill 摘要。 |
| `kimi_cycle/workspace_tasks.py` | 定义 Kimi worker 的任务目录和输出契约。 |
| `kimi_cycle/eval_generation.py` | 让 Kimi 生成新的 eval draft。 |
| `kimi_cycle/skill_rewrite.py` | 让 Kimi 生成 skill rewrite draft。 |
| `kimi_cycle/kimi_cli.py` | Kimi CLI 调用兼容层，workspace task 复用共享 runtime。 |
| `run_kimi_production_cycle.py` | 生产循环 CLI。 |

Kimi worker 输出示例：

- `outputs/eval-draft.json`
- `outputs/SKILL.generated.md`
- `outputs/run-report.json`

关键约束：

- Kimi 不负责最终拍板。
- Kimi 不需要在终端返回完整大文件。
- Codex 必须读取输出文件、验证、应用、评测，再决定下一轮。

## 13. Validator 功能

Validators 是低成本质量门禁。

| Validator | 检查内容 |
| --- | --- |
| `package_validator.py` | package 是否有必需文件、frontmatter、metadata 字段、evals 字段。 |
| `protocol_validator.py` | `SKILL.md` 是否包含当前要求的协议结构、Step、输出和规则块。 |

定位：

- Validator 只能证明“结构没有明显坏掉”。
- Validator 不能证明 skill 真的更有用。
- skill 质量主要看 differential benchmark、analysis、host validation 和 human review。

## 14. 主要产物速查

| 产物 | 生成阶段 | 用途 |
| --- | --- | --- |
| `evals/evals.json` | eval sync | package 当前消费的评测集。 |
| `eval_metadata.json` | prepare iteration | 单个 eval 的运行元信息。 |
| `request.json` | executor | 本次 run 的输入、配置、turn script。 |
| `raw_response.json` | executor | Kimi 调用日志、workspace task 元数据。 |
| `transcript.json` | executor | 标准化后的对话记录。 |
| `outputs/final_response.md` | executor | run 的完整多轮对话，后续评分默认读取它。 |
| `outputs/latest_assistant_response.md` | executor | 最后一轮 assistant 回答，供 deep eval 和调试区分最终单答。 |
| `timing.json` | executor | 执行耗时和 token 占位字段。 |
| `grading.json` | grader | 单次回答的 expectation 检查结果。 |
| `benchmark.json` | gate benchmark | 支持性 pass rate 和执行指标。 |
| `differential-benchmark.json` | differential benchmark | Level 3 主价值判断。 |
| `level3-summary.json` | Level 3 summary | Level 4-6 的统一入口。 |
| `stability.json` | Level 4 | 稳定性结论。 |
| `analysis.json` | Level 5 | 机制分析和修复建议。 |
| `failure-tags.json` | Level 5 | 失败标签统计。 |
| `human-review-packet.md` | Level 6 | 给人工审核的证据包。 |
| `human-review-score.json` | Level 6 | 人工审核填写模板。 |
| `release-recommendation.json` | Level 6 | 系统生成的放行建议。 |
| `host-benchmark.json` | Host lane | 真实宿主 trigger 和协议指标。 |

## 15. 常用命令

安装开发依赖：

```bash
pip install -e .[dev]
```

运行全量测试：

```bash
python -m pytest
```

跑主评测链：

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --runs-per-configuration 3
```

跑轻量 smoke：

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --smoke
```

单独跑 Level 4-6：

```bash
python -m toolchain.run_level456 --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

跑 host validation：

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace" --iteration-number 1 --max-evals 4
```

跑 Kimi 生产循环：

```bash
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\golden-circle" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\golden-circle-workspace" --apply-generated-evals --apply-skill --run-eval
```

## 16. 开发者应该如何使用这套工程

### 16.1 新建或迁移 skill

推荐顺序：

```text
demo/source
  -> package skeleton
  -> SKILL.md lightweight behavior contract
  -> metadata/source-map
  -> evals
  -> validator
  -> smoke eval
  -> full eval
```

先保证 package 进入标准结构，再做质量优化。

### 16.2 优化已有 skill

推荐顺序：

```text
read latest level3-summary / differential-benchmark / analysis
  -> identify one primary failure mode
  -> write or update optimization brief
  -> edit one high-impact part of SKILL.md
  -> run validator
  -> rerun same eval set
  -> compare with previous iteration
```

优先修改：

- Step 0 路由
- direct-result 分支
- missing-info 分支
- staged 分支
- checkpoint 规则
- 输出骨架
- 少量高质量 examples

避免同一轮混改：

- trigger description
- 主体协议
- eval 扩容
- host lane 扩容
- 长参考材料

### 16.3 判断是否可以推进

可推进的证据：

- package validator 通过。
- `differential-benchmark.json` 不再显示明显负向。
- `level3-summary.json` 有清晰 Level 3 主信号。
- `stability.json` 没有关键不稳定风险。
- `analysis.json` 的主失败模式已变化或减轻。
- host validation 显示真实宿主能触发并执行协议。
- human review 给出 `pass` 或明确可修复的 `revise`。

不能推进的情况：

- 只有格式通过，没有差分收益。
- `with_skill` 比 baseline 更啰嗦但用户价值更低。
- staged interaction 变成仪式化暂停。
- Kimi 终端说成功，但 required output files 缺失或不合规。
- 没有人审，却宣称 release quality。

## 17. 当前边界

当前已经具备：

- 标准 package 结构。
- certified eval sync。
- Kimi Code workspace-file 主执行链。
- gate benchmark 和 differential benchmark。
- Level 4 稳定性分析。
- Level 5 机制分析。
- Level 6 人审 packet 和 release recommendation。
- Kimi Code host validation。
- Codex 控制的 Kimi production cycle。

当前仍需持续建设：

- 更多 package 的 certified eval 覆盖。
- 更多真实 host eval case。
- 更稳定的 skill 优化循环样板。
- 更细的 release gate 策略。
- 更清晰的人工审核流程和历史结果沉淀。

## 18. 一句话工作模型

```text
Codex 是总控。
Kimi Code 是执行者、judge、analyzer 或 worker。
所有关键结果必须落到受控文件。
所有质量判断必须回到 eval artifacts。
所有发布结论必须经过人工审核。
```
