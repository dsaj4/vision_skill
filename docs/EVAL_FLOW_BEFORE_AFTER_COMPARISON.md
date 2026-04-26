# 评测流程改造前后完整对比

Last updated: 2026-04-26

本文用于对比当前评测流程和下一版收束后的评测流程，帮助开发者理解整体代码逻辑、数据流和 artifact 变化。

当前状态：改造后流程已经接入默认主链。后续阅读本文时，可把“改造后”理解为当前主流程，把“改造前”理解为历史兼容流程。

当前默认入口：

```text
python -m toolchain.run_eval_pipeline
```

当前 post-execution 兼容入口：

```text
python -m toolchain.run_level456
```

其中 `run_level456` 已从旧的 `stability -> analysis -> review` 改为 `hard gate -> quantitative summary -> deep eval -> review`。

## 1. 为什么要改

当前系统已经形成完整的工程链路，但前期评测层承担了太多质量判断职责：

- 规则型 grading 更适合检查格式、非空、关键词、基础结构，不适合判断高质量思考。
- differential benchmark 能比较 with_skill 和 without_skill，但容易把 judge 结论变成唯一主信号。
- stability 依赖 rule grading 和结构 fingerprint，能发现波动，但对内容质量解释不足。
- mechanism analysis 读取了过多前置定量产物，导致输入复杂，结论容易围绕旧指标展开。

改造目标是把评测职责重新分层：

```text
Hard Gate: 能不能评
Quantitative Bundle: 有哪些支持性量化信号
Deep Quality Eval: 内容质量到底怎么样
Human Review: 是否最终放行
```

## 2. 改造前流程

当前默认主链：

```text
sync
  -> prepare
  -> execute
  -> grade
  -> benchmark
  -> differential benchmark
  -> level3-summary
  -> stability
  -> analysis
  -> human review packet
  -> release recommendation
```

代码入口：

```text
toolchain.run_eval_pipeline
```

当前 `run_eval_pipeline` 大致执行顺序：

```text
sync_package_evals
  -> prepare_iteration
  -> execute_iteration
  -> grade_iteration_runs
  -> run_differential_benchmark
  -> generate_level3_summary
  -> run_level456
```

`run_level456` 内部：

```text
ensure_level3_summary
  -> generate_stability_report
  -> analyze_iteration
  -> build_human_review_packet
  -> generate_release_recommendation
```

### 2.1 改造前的关键依赖

```text
run artifacts
  -> grading.json
  -> benchmark.json
  -> differential-benchmark.json
  -> level3-summary.json
  -> stability.json
  -> analysis.json
  -> human-review-packet.md
  -> release-recommendation.json
```

特点：

- `analysis.json` 依赖 `benchmark.json`、`stability.json`、`level3-summary.json`。
- `human-review-packet.md` 依赖 `benchmark.json`、`stability.json`、`analysis.json`。
- `release-recommendation.json` 依赖 `level3-summary.json`、`stability.json`、`analysis.json` 和人工 review。
- `level3-summary.json` 是 Level 4-6 的主入口。

### 2.2 改造前的优点

- 链路完整。
- 产物丰富。
- 能做基础回归。
- 能比较 with_skill 和 without_skill。
- 旧 artifact 可复查。

### 2.3 改造前的不足

- Level 1-3 太重，很多指标不直接服务高质量 skill 优化。
- pass rate 和格式命中可能误导开发者优化表面结构。
- 深度分析被前置定量结果牵引，不够直接观察原始回答质量。
- review packet 可读性受复杂指标影响。
- release recommendation 容易把 win rate、cost-adjusted value 等当成强判断。

## 3. 改造后流程

下一版默认主链：

```text
sync
  -> prepare
  -> execute
  -> hard gate
  -> quantitative bundle
  -> deep quality eval
  -> human review packet
  -> release recommendation
```

新的代码入口仍保留：

```text
toolchain.run_eval_pipeline
```

新的内部执行顺序建议：

```text
sync_package_evals
  -> prepare_iteration
  -> execute_iteration
  -> run_hard_gate
  -> run_quantitative_bundle
  -> run_deep_eval
  -> build_human_review_packet
  -> generate_release_recommendation
```

### 3.1 改造后的关键依赖

```text
run artifacts
  -> hard-gate.json
  -> quantitative-summary.json
  -> deep-eval.json
  -> human-review-packet.md
  -> release-recommendation.json
```

其中：

- `hard-gate.json` 判断是否可评。
- `quantitative-summary.json` 汇总定量支持证据。
- `deep-eval.json` 是主质量判断。
- `human-review-packet.md` 主要展示 deep eval 和代表性原始回答。
- `release-recommendation.json` 主要依据 hard gate、deep eval、人审结果。

## 4. 阶段职责对比

| 阶段 | 改造前职责 | 改造后职责 |
| --- | --- | --- |
| `sync` | 同步 package evals | 保持不变。 |
| `prepare` | 创建 iteration 目录 | 保持不变。 |
| `execute` | 生成 with_skill / without_skill 回答 | 支持 `execution_eval.turn_script` 驱动的 scripted multi-turn，继续用 Kimi workspace-file task。 |
| `grade` | 规则型评分，进入 benchmark | 降级为 quantitative bundle 内部步骤。 |
| `benchmark` | 聚合 pass rate、time、tokens | 降级为 supporting artifact。 |
| `differential` | Level 3 主价值判断 | 降级为 supporting artifact。 |
| `level3-summary` | Level 4-6 主入口 | 保留兼容，不再是 deep eval 必需输入。 |
| `stability` | Level 4 稳定性判断 | 迁入 quantitative bundle，作为 supporting risk。 |
| `analysis` | Level 5 机制分析 | 升级/替换为 deep quality eval。 |
| `review` | 读取 Level 3-5 产物生成 packet | 优先读取 deep eval 和原始代表性回答。 |
| `recommendation` | 结合 level3、stability、analysis、人审 | 结合 hard gate、deep eval、quantitative supporting、人审。 |

## 5. Artifact 对比

### 5.1 保留不变

| Artifact | 说明 |
| --- | --- |
| `evals/evals.json` | package 当前消费的 eval。 |
| `eval_metadata.json` | 单个 eval 的运行元信息。 |
| `request.json` | run 请求、配置、`execution_eval` 和 turn script。 |
| `raw_response.json` | Kimi 调用日志和 workspace task 元数据。 |
| `transcript.json` | 标准化多轮对话记录。 |
| `outputs/final_response.md` | run 完整多轮对话。 |
| `outputs/latest_assistant_response.md` | 最后一轮 assistant 回答。 |
| `timing.json` | 执行耗时和 token 占位。 |
| `human-review-score.json` | 人工审核填写文件。 |

### 5.2 降级为 supporting

| Artifact | 改造后定位 |
| --- | --- |
| `grading.json` | Quantitative Bundle 内部 run 级规则检查。 |
| `benchmark.json` | Supporting benchmark。 |
| `differential-benchmark.json` | Supporting pairwise evidence。 |
| `level3-summary.json` | 兼容旧流程的归一化摘要。 |
| `stability.json` | Supporting stability risk。 |

### 5.3 新增

| Artifact | 作用 |
| --- | --- |
| `hard-gate.json` | 判断 run artifacts 是否完整、回答是否非空、是否可进入 deep eval。 |
| `hard-gate.md` | Hard gate 可读报告。 |
| `quantitative-summary.json` | 定量脚本统一输出摘要。 |
| `quantitative-summary.md` | 定量支持证据可读报告。 |
| `deep-eval.json` | 主质量判断。 |
| `deep-eval.md` | 深度评测可读报告。 |
| `quality-failure-tags.json` | 内容质量失败标签统计。 |

### 5.4 替换主地位

| 改造前主信号 | 改造后主信号 |
| --- | --- |
| `level3-summary.pairwise_summary` | `deep-eval.release_signal` |
| `benchmark.run_summary` | `hard-gate.passed` 和 `deep-eval.per_eval` |
| `analysis.json` | `deep-eval.json` |

## 6. 数据流对比

### 6.1 改造前数据流

```text
final_response.md
  -> grading.json
  -> benchmark.json
  -> level3-summary.json
  -> stability.json
  -> analysis packet
  -> analysis.json
  -> review packet
```

问题：

- Deep analysis 的输入绕了一圈定量层。
- 原始回答只是 excerpt，容易被中间指标压过。
- 分析结论可能过度解释 pass rate、win rate、stability flags。

### 6.2 改造后数据流

```text
final_response.md + latest_assistant_response.md + request.json + transcript.json + raw_response.json + timing.json + SKILL.md + rubric
  -> deep eval packet
  -> deep-eval.json
  -> review packet
```

同时：

```text
final_response.md
  -> quantitative bundle
  -> quantitative-summary.json
  -> review supporting section
```

优势：

- Deep Eval 直接看原始回答和上下文。
- 定量指标不再干扰主质量判断。
- Review packet 更接近人类审阅方式。
- 修复建议可以直接指向内容问题，而不是指标问题。

## 7. 代码入口对比

### 7.1 默认 pipeline

改造前：

```text
toolchain.run_eval_pipeline
  -> grade_iteration_runs
  -> run_differential_benchmark
  -> generate_level3_summary
  -> run_level456
```

改造后：

```text
toolchain.run_eval_pipeline
  -> run_hard_gate
  -> run_quantitative_bundle
  -> run_deep_eval
  -> build_human_review_packet
  -> generate_release_recommendation
```

### 7.2 Level 4-6

改造前：

```text
toolchain.run_level456
  -> stability
  -> analysis
  -> review
  -> recommendation
```

改造后：

```text
toolchain.run_level456
  -> compatibility wrapper
  -> may call quantitative bundle + deep eval + review
```

`run_level456` 不再是推荐主入口，只保留为兼容和调试入口。

### 7.3 Deep Eval

新增：

```text
python -m toolchain.deep_evals.run_deep_eval --iteration-dir ... --package-dir ...
```

职责：

- 构造 packet。
- 调用 Kimi workspace-file task。
- 校验 `outputs/deep-eval.json`。
- 写主评测产物。

### 7.4 Quantitative Bundle

新增：

```text
python -m toolchain.quantitative.run_quantitative_bundle --iteration-dir ... --package-dir ...
```

职责：

- 集中运行旧定量脚本。
- 生成旧兼容 artifacts。
- 汇总 `quantitative-summary.json`。

## 8. 开发者如何阅读新流程

建议阅读顺序：

1. 先看本文，理解改造前后流程差异。
2. 再看 `docs/EVAL_SYSTEM_REFACTOR_PLAN_V1.md`，理解实施方案。
3. 再看 `toolchain/run_eval_pipeline.py`，理解默认入口如何串联。
4. 再看 `toolchain/deep_evals/`，理解主质量判断。
5. 再看 `toolchain/quantitative/`，理解 supporting metrics。
6. 最后看 `toolchain/reviews/`，理解人工审核和 release recommendation。

调试建议：

- 如果 run 没有产物，先看 `hard-gate.json`。
- 如果内容质量不稳定，先看 `deep-eval.json`。
- 如果需要辅助定位格式、稳定性或 pairwise 信号，再看 `quantitative-summary.json`。
- 如果准备放行，必须看 `human-review-packet.md` 和 `human-review-score.json`。

## 9. 迁移注意事项

### 9.1 旧测试兼容

旧测试可能直接断言：

- `benchmark.json` 存在。
- `differential-benchmark.json` 存在。
- `level3-summary.json` 存在。
- `analysis.json` 存在。

迁移时不要第一轮删除这些产物。应先保持生成，再新增 deep eval 产物。

### 9.2 旧文档表述

需要逐步替换旧说法：

| 旧说法 | 新说法 |
| --- | --- |
| Level 3 是主价值判断 | Deep Quality Eval 是主质量判断。 |
| `differential-benchmark.json` 是主信号 | `differential-benchmark.json` 是 supporting evidence。 |
| Level 4-6 消费 `level3-summary.json` | Deep Eval 直接消费 run artifacts。 |
| `analysis.json` 是机制分析主产物 | `deep-eval.json` 是主深度评测产物。 |

### 9.3 旧 CLI 入口

旧 CLI 不要立即删除：

- `toolchain.benchmarks.run_benchmark`
- `toolchain.benchmarks.run_differential_benchmark`
- `toolchain.run_level456`

它们应被标注为 advanced/internal compatibility commands。

### 9.4 历史 artifacts

历史 iteration 里可能没有：

- `hard-gate.json`
- `quantitative-summary.json`
- `deep-eval.json`

读取历史 workspace 时，要允许缺失新产物，并提示该 iteration 属于旧流程。

### 9.5 Release 判断

改造后不应只看：

- pass rate
- win rate
- avg margin
- cost-adjusted value

应优先看：

- hard gate 是否通过。
- deep eval 是否认为内容质量足够。
- failure tags 是否可接受。
- human review 是否通过。
- quantitative bundle 是否暴露关键 supporting risk。
