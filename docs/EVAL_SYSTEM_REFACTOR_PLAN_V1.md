# 评测系统收束计划 V1

Last updated: 2026-04-26

本文用于固定下一阶段评测系统改造方向：让深度评测成为 skill 质量主判断，让前期定量层降噪，并把现有定量脚本统一打包为 supporting evidence。

当前实现状态：第一版主链已经按本文落地。`toolchain.run_eval_pipeline` 默认执行 `sync -> prepare -> execute -> hard gate -> quantitative bundle -> deep quality eval -> human review packet -> release recommendation`；`toolchain.run_level456` 已改为兼容性的 post-execution 入口，不再默认生成旧 `analysis.json`。

已落地 artifact：

- `hard-gate.json` / `hard-gate.md`
- `quantitative-summary.json` / `quantitative-summary.md`
- `deep-eval.json` / `deep-eval.md`
- `quality-failure-tags.json`
- `human-review-packet.md`
- `release-recommendation.json`

当前判定边界：

- `hard-gate.json` 只判断是否可评，不判断质量。
- `quantitative-summary.json` 只作为 supporting evidence。
- `deep-eval.json` 是机器侧主要质量判断。
- `human-review-score.json` 仍是最终人工裁决。

## 1. 背景与问题

当前评测系统已经能跑通完整链路：

```text
sync evals
  -> prepare iteration
  -> execute with_skill / without_skill
  -> grade
  -> benchmark
  -> differential benchmark
  -> level3-summary
  -> stability
  -> analysis
  -> human review
  -> release recommendation
```

这条链路的问题不是不能用，而是对高质量 skill 优化已经偏重：

- Level 1-3 产生了大量结构和定量指标，但这些指标更擅长发现“坏掉了没有”，不擅长判断“内容是否真的更好”。
- `pass_rate`、expectation 命中、结构 fingerprint 等指标容易让开发者优化格式，而不是优化用户价值。
- 后续深度评测仍要读取 `benchmark.json`、`level3-summary.json`、`stability.json` 等中间产物，导致分析 packet 噪音变多。
- 对高质量 skill 来说，关键问题往往在回答内容、判断质量、思考支持、语气和边界，而不是几个固定关键词是否命中。
- 现有 Level 4-6 名义上是深度层，但输入仍被前期定量结果强影响，可读性有限。

因此，下一版要把“能不能评”和“好不好”分开：

```text
Hard Gate 判断是否可评。
Quantitative Bundle 提供支持性指标。
Deep Quality Eval 负责主要质量判断。
Human Review 负责最终放行。
```

## 2. 目标架构

新架构保留当前工程主线，但重新划分职责。

| 层级 | 新定位 | 说明 |
| --- | --- | --- |
| Level 1-3 | Hard Gate | 只判断 artifact 是否完整、回答是否非空、执行是否失败、是否具备进入深度评测的最低条件。 |
| Quantitative Bundle | Supporting Evidence | 统一打包旧的 rule grading、benchmark、differential、stability。默认生成，但不作为质量主判断。 |
| Deep Quality Eval | 主质量判断 | 直接读取原始回答和 run artifacts，由大模型按内容质量标准评估。 |
| Human Review | 最终裁决 | 读取 deep eval 和 supporting evidence，决定 `pass / revise / hold`。 |

核心原则：

- 不再让 `benchmark.json` 或 `level3-summary.json` 决定 skill 质量。
- 深度评测直接消费原始模型回答、transcript、request、raw_response、timing 和 SKILL 摘要。
- 定量指标保留，但只帮助定位风险，不替代内容判断。
- Kimi Code 继续使用 workspace-file task，所有关键结果必须落文件。
- 人工审核仍是最终 release gate。

## 3. 新主链

默认主链调整为：

```text
sync evals
  -> prepare iteration
  -> execute with_skill / without_skill
  -> hard gate
  -> quantitative bundle
  -> deep quality eval
  -> human review packet
  -> release recommendation
```

阶段说明：

| 阶段 | 输入 | 输出 | 作用 |
| --- | --- | --- | --- |
| `sync evals` | package metadata、certified bundle | `evals/evals.json` | 确保 package 使用最新评测集。 |
| `prepare iteration` | package evals | `iteration-N/eval-*` | 创建运行目录和 eval metadata。 |
| `execute` | eval metadata、package skill | run artifacts | 通过 Kimi Code 生成 with_skill 和 without_skill 原始回答。 |
| `hard gate` | run artifacts | `hard-gate.json` | 判断是否具备进入深度评测的最低条件。 |
| `quantitative bundle` | run artifacts、grading rules | `quantitative-summary.json` 和旧兼容产物 | 提供 supporting quantitative evidence。 |
| `deep quality eval` | 原始回答、run artifacts、rubric、SKILL 摘要 | `deep-eval.json` | 生成主质量判断、失败归因、修复建议。 |
| `human review packet` | deep eval、quantitative summary、代表性回答 | `human-review-packet.md` | 给人工审核整理证据。 |
| `release recommendation` | hard gate、deep eval、human review | `release-recommendation.json` | 给出系统建议，不替代人工裁决。 |

默认仍跑 Quantitative Bundle，但它的结论只进入 supporting section。

## 4. 模块设计

### 4.1 `hard_gates/`

新增模块建议：

```text
toolchain/hard_gates/
  run_hard_gate.py
  artifact_gate.py
```

职责：

- 检查每个 run 是否存在 `request.json`、`raw_response.json`、`transcript.json`、`timing.json`、`outputs/final_response.md`。
- 检查回答是否为空。
- 检查是否存在 `execution_error.json`。
- 检查 final response 文件是否可读。
- 汇总 iteration 级别是否可进入 deep eval。

不做：

- 不判断回答是否好。
- 不计算 skill 是否赢 baseline。
- 不生成复杂内容指标。

### 4.2 `quantitative/`

新增模块建议：

```text
toolchain/quantitative/
  run_quantitative_bundle.py
  summary.py
```

职责：

- 统一运行旧定量能力：rule grading、supporting benchmark、pairwise differential、stability。
- 继续写旧兼容产物：`benchmark.json`、`differential-benchmark.json`、`level3-summary.json`、`stability.json`。
- 新增统一入口产物：`quantitative-summary.json`。
- 在 summary 中明确标注这些指标是 supporting evidence。

不做：

- 不作为 release 主门槛。
- 不阻止 deep eval，除非 hard gate 已失败。
- 不把 pass rate 或 win rate 当作 skill 质量主结论。

### 4.3 `deep_evals/`

新增模块建议：

```text
toolchain/deep_evals/
  packet_builder.py
  quality_rubric.py
  run_deep_eval.py
  normalizer.py
```

职责：

- 从 iteration 中直接读取原始回答和 run artifacts。
- 构造 deep eval packet。
- 合并全局 VisionTree rubric 和 package/eval 级 rubric。
- 通过 Kimi workspace-file task 要求写 `outputs/deep-eval.json`。
- 归一化 deep eval 输出。
- 写 `deep-eval.json`、`deep-eval.md`、`quality-failure-tags.json`。

Deep Eval 直接读取：

- `eval_metadata.json`
- `with_skill/run-*/outputs/final_response.md`
- `without_skill/run-*/outputs/final_response.md`
- `request.json`
- `transcript.json`
- `raw_response.json`
- `timing.json`
- `packages/<package>/SKILL.md`
- package metadata
- global quality rubric

Deep Eval 不必读取：

- `benchmark.json`
- `differential-benchmark.json`
- `level3-summary.json`
- `stability.json`

这些可以作为 optional supporting evidence，但不能成为主输入依赖。

### 4.4 Review / Recommendation 改造

`reviews/` 保留，但证据优先级调整：

1. `deep-eval.json`
2. 原始代表性回答
3. `quantitative-summary.json`
4. 旧兼容定量产物
5. 人工填写的 `human-review-score.json`

`release-recommendation.json` 的最低判断逻辑调整为：

- hard gate 是否通过。
- deep eval 是否完成。
- deep eval 建议是 `pass / revise / hold`。
- human review 是否完成。
- quantitative bundle 是否有 supporting blockers。

最终 release 决定仍以人工审核为准。

## 5. Artifact Contract

### 5.1 `hard-gate.json`

建议结构：

```json
{
  "metadata": {},
  "passed": true,
  "blockers": [],
  "per_run": []
}
```

`blockers` 示例：

- `missing_request`
- `missing_raw_response`
- `missing_transcript`
- `missing_timing`
- `missing_final_response`
- `empty_final_response`
- `execution_error`

### 5.2 `quantitative-summary.json`

建议结构：

```json
{
  "metadata": {
    "role": "supporting-evidence"
  },
  "artifacts": {},
  "gate_summary": {},
  "pairwise_summary": {},
  "stability_summary": {},
  "supporting_risks": []
}
```

它可以引用旧产物路径，但不能声明 release decision。

### 5.3 `deep-eval.json`

建议结构：

```json
{
  "metadata": {},
  "rubric": {},
  "per_eval": [],
  "cross_eval_summary": {},
  "repair_recommendations": [],
  "release_signal": {},
  "evidence_index": {}
}
```

`per_eval` 至少包含：

- `eval_id`
- `prompt`
- `with_skill_assessment`
- `without_skill_assessment`
- `comparative_judgment`
- `quality_findings`
- `failure_tags`
- `repair_layer`
- `evidence_refs`

`release_signal.decision` 只允许：

- `pass`
- `revise`
- `hold`

### 5.4 `quality-failure-tags.json`

用于统计内容质量层失败：

```json
{
  "metadata": {},
  "counts": {},
  "per_eval": []
}
```

失败标签应更贴近内容质量，例如：

- `quality.reasoning-shallow`
- `quality.user-value-weak`
- `quality.judgment-preservation-weak`
- `quality.actionability-weak`
- `quality.boundary-safety-weak`
- `quality.voice-drift`
- `protocol.direct-result-friction`
- `protocol.staged-ceremony`

## 6. 兼容策略

保留旧产物，但降低权重：

| 旧产物 | 新定位 |
| --- | --- |
| `grading.json` | Quantitative Bundle 内部输入。 |
| `benchmark.json` | Supporting artifact。 |
| `differential-benchmark.json` | Supporting artifact。 |
| `level3-summary.json` | 兼容旧 Level 4-6 的归一化产物。 |
| `stability.json` | Supporting risk artifact。 |
| `analysis.json` | 后续由 `deep-eval.json` 替代主地位，可保留兼容。 |
| `human-review-packet.md` | 继续保留，但内容优先展示 deep eval。 |
| `release-recommendation.json` | 保留名称，内部逻辑改为基于 hard gate + deep eval + human review。 |

CLI 兼容：

- `python -m toolchain.run_eval_pipeline` 保留为默认入口。
- `python -m toolchain.benchmarks.run_differential_benchmark` 保留为 advanced/internal command。
- `python -m toolchain.run_level456` 保留兼容，但文档标注为旧式后处理入口。
- 新增 `python -m toolchain.deep_evals.run_deep_eval`。
- 新增 `python -m toolchain.quantitative.run_quantitative_bundle`。

## 7. 实施步骤

建议按 5 个小步实施。

1. 新增 Hard Gate
   - 实现 run artifact 完整性检查。
   - 输出 `hard-gate.json` 和 `hard-gate.md`。
   - 在 pipeline 中插入 execute 之后。

2. 新增 Quantitative Bundle
   - 把现有 grading、benchmark、differential、stability 串到一个统一入口。
   - 输出 `quantitative-summary.json`。
   - 保持旧 artifacts 继续生成。

3. 新增 Deep Quality Eval
   - 实现 packet builder。
   - 实现全局 + 包级 rubric 合并。
   - 使用 Kimi workspace-file task 写 `outputs/deep-eval.json`。
   - 输出 `deep-eval.json`、`deep-eval.md`、`quality-failure-tags.json`。

4. 改造 Review / Recommendation
   - `human-review-packet.md` 优先读取 deep eval。
   - representative runs 优先来自 deep eval evidence refs。
   - release recommendation 以 hard gate、deep eval、human review 为主。

5. 文档和测试收口
   - 更新 README、PROJECT、STRUCTURE_AND_FUNCTIONS、toolchain README。
   - 标注旧 Level 1-3 指标为 supporting。
   - 补齐单元测试和 synthetic integration test。

## 8. 测试计划

必须新增或调整：

- Hard Gate 测试
  - 缺 final response 时失败。
  - 空回答时失败。
  - 有 `execution_error.json` 时失败。
  - artifacts 完整且回答非空时通过。

- Deep Eval Packet 测试
  - packet 能直接读取原始回答和 run artifacts。
  - 不依赖 `benchmark.json` 或 `level3-summary.json`。
  - SKILL 摘要和 rubric 能进入 packet。

- Rubric 测试
  - 全局 rubric 必定存在。
  - package/eval 级 rubric 能追加。
  - 必需维度不能被删除。

- Kimi Workspace 测试
  - fake runner 写 `outputs/deep-eval.json` 后能被读取。
  - 终端回文不作为结果源。
  - 缺 required output 时失败。

- Quantitative Bundle 测试
  - 能生成旧兼容 artifacts。
  - 能生成 `quantitative-summary.json`。
  - summary 明确标注 role 为 supporting evidence。

- Pipeline 集成测试
  - synthetic package 跑通新默认链。
  - 最终存在 `hard-gate.json`、`quantitative-summary.json`、`deep-eval.json`、`human-review-packet.md`、`release-recommendation.json`。

验收标准：

- Deep Eval 可以在没有 `benchmark.json` 的情况下构造 packet。
- `run_eval_pipeline` 默认产出 deep eval。
- release recommendation 不再把 `win_rate` 或 `pass_rate` 当作主判断。
- 旧定量产物仍可按兼容路径生成。

## 9. 默认假设

- 本轮目标是评测系统架构收束，不直接优化具体 skill 内容。
- 默认双轨都运行：deep eval 是主质量判断，quantitative bundle 是 supporting evidence。
- 不删除旧模块，只迁移主入口和文档权重。
- Kimi Code 仍是默认模型执行方式。
- 所有 Kimi 结果继续使用 workspace-file task。
- Human Review 仍是最终放行点。
- Host validation 暂不纳入本轮主链重构，后续可作为 deep eval 的扩展输入。
