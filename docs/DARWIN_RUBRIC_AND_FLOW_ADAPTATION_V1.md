# Darwin Skill Rubric 与流程借鉴改造方案 V1

Last updated: 2026-04-25

本文基于本地参考工程 `E:\Project\vision-lab\darwin-skill`，用于说明如何借鉴 Darwin Skill 的评分系统与架构设计，改进当前 `vision-skill` 的评测主链。

本文最初用于方案设计；当前已开始按该方案落地第一阶段保守版实现。

Implementation note:

当前代码已开始落地第一阶段保守版：

| 项目 | 当前状态 |
| --- | --- |
| Deep Eval 全局维度 | 已收窄为 Darwin 明确映射的 `Overall Structure` 与 `Live Test Performance`。 |
| Package rubric | 已支持从 `metadata/package.json` 的 `quality_rubric` 或 `metadata/quality-rubric.json` 读取。 |
| Eval rubric | 已支持从 eval case 的 `quality_rubric` 读取。 |
| Quantitative structural diagnostics | 已把 Darwin 1-6 维迁移为 `quantitative-summary.json` 中的 diagnostic-only 结构诊断。 |
| Release gate | 未引入 100 分总分，仍保持 `hard gate + deep eval + human review`。 |

## 1. 阅读结论

`darwin-skill` 不是一个复杂代码库，它更像一个完整的 skill 优化方法论。核心思想可以概括为：

```text
Evaluate
  -> Improve
  -> Test
  -> Human Confirm
  -> Keep or Revert
  -> Repeat
```

它对 `vision-skill` 最有价值的不是某段实现，而是四个工程原则：

| Darwin 设计 | 对 vision-skill 的启发 |
| --- | --- |
| 8 维 100 分评分 | 把 skill 质量拆成结构、协议、资源、实测效果等可讨论维度。 |
| Structure + Effectiveness 双评估 | 不能只看 `SKILL.md` 是否规范，也不能只看模型回答是否好看。 |
| Ratchet 机制 | 每轮优化必须证明有增益，否则不应进入新基线。 |
| Independent scoring | 修改 skill 的 agent 和评分 agent 应隔离，减少自评偏差。 |
| Human in the loop | 最终放行不自动化，系统只整理证据和建议。 |

这些原则与当前项目方向一致，但不能照搬 Darwin 的“总分 100 直接决策”。当前 `vision-skill` 已经明确把质量主判断交给 `deep-eval.json`，因此 Darwin 的量化分数应被拆分到 `hard gate` 和 `quantitative bundle` 中，作为诊断和回归证据，而不是重新成为 release gate。

## 2. Darwin 8 维评分拆解

Darwin Skill 的评分体系是 8 维、100 分：

| 维度 | 权重 | 原始含义 | 建议归属 |
| --- | ---: | --- | --- |
| Frontmatter 质量 | 8 | `name`、`description`、触发描述、长度规范。 | Quantitative Bundle |
| 工作流清晰度 | 15 | 步骤明确、可执行、有输入输出。 | Quantitative Bundle + Deep Eval |
| 边界条件覆盖 | 10 | 异常、fallback、错误恢复。 | Hard Gate + Quantitative Bundle + Deep Eval |
| 检查点设计 | 7 | 关键决策前确认，避免自主失控。 | Quantitative Bundle + Deep Eval |
| 指令具体性 | 15 | 不模糊，有参数、格式、示例，可执行。 | Quantitative Bundle + Deep Eval |
| 资源整合度 | 5 | references、scripts、assets 引用正确。 | Hard Gate + Quantitative Bundle |
| 整体结构 | 15 | 层次清晰，不冗余不遗漏，与生态一致。 | Deep Eval |
| 实测表现 | 25 | 跑真实 prompt 后，输出是否符合 skill 宣称能力。 | Deep Eval + Quantitative Bundle |

拆分原则：

| 类型 | 放在哪里 | 原因 |
| --- | --- | --- |
| 文件是否存在、JSON 是否可读、路径是否有效、输出是否为空 | Hard Gate | 这是“是否可评”，不是“是否优秀”。 |
| frontmatter 长度、字段覆盖、步骤数量、资源链接、checkpoint 标记、运行成本、稳定性 | Quantitative Bundle | 可机械统计，适合做诊断，不适合直接定生死。 |
| 回答是否真的有用户价值、是否自然、是否帮助思考、checkpoint 是否有编辑价值 | Deep Quality Eval | 需要模型或人工判断内容质量。 |
| 是否放行 | Human Review | 不能被总分替代。 |

## 3. Rubric 改造目标

当前 `deep_evals/quality_rubric.py` 已有全局质量维度：

```text
User Value
Thinking Support
Judgment Preservation
Specificity
Actionability
Boundary Safety
Natural Voice
VisionTree Voice
```

这套维度方向正确，但还缺两件事：

| 缺口 | 改进方式 |
| --- | --- |
| 与结构诊断没有明确分工 | 把 Darwin 的可量化结构项迁移到 Quantitative Bundle。 |
| 与 package/eval 级标准合并较弱 | 引入三层 rubric 合并：global、package、eval。 |

目标不是把 deep eval 变成 100 分表，而是让 deep eval 使用更清晰的内容质量标准，同时让可数、可验、可回归的指标进入 supporting bundle。

## 4. 新 Rubric 分层设计

建议将 rubric 拆成三层。

### 4.1 Hard Gate Rubric

回答的问题：

```text
这一轮是否具备进入评测的最低条件？
```

建议检查项：

| 检查项 | 失败码 | 处理 |
| --- | --- | --- |
| `SKILL.md` 存在 | `missing_skill` | 阻断 |
| package metadata 存在且可读 | `missing_package_metadata` | 阻断 |
| eval 文件存在且可读 | `missing_evals` | 阻断 |
| run artifacts 完整 | `missing_run_artifact` | 阻断 |
| final response 非空 | `empty_final_response` | 阻断 |
| execution error 不存在 | `execution_error` | 阻断 |
| required output 文件可读 | `unreadable_output` | 阻断 |

当前已实现部分：

| 已实现 | 位置 |
| --- | --- |
| run artifacts 完整性检查 | `toolchain/hard_gates/artifact_gate.py` |
| 空回答检查 | `toolchain/hard_gates/artifact_gate.py` |
| execution error 检查 | `toolchain/hard_gates/artifact_gate.py` |

后续可补充：

| 待补 | 建议 |
| --- | --- |
| package 级 hard gate | 增加 `package_gate.py`，检查 `SKILL.md`、metadata、evals。 |
| eval source hard gate | 检查 certified bundle sync 后的 `evals/evals.json` 是否为空或字段缺失。 |

### 4.2 Quantitative Rubric

回答的问题：

```text
这个 skill 的结构、协议、资源和运行指标有哪些可量化风险？
```

建议新增 `structural_diagnostics`，纳入 `quantitative-summary.json`。

建议结构：

```json
{
  "structural_diagnostics": {
    "frontmatter_quality": {
      "weight": 8,
      "score": 0,
      "checks": []
    },
    "workflow_clarity": {
      "weight": 15,
      "score": 0,
      "checks": []
    },
    "boundary_coverage": {
      "weight": 10,
      "score": 0,
      "checks": []
    },
    "checkpoint_design": {
      "weight": 7,
      "score": 0,
      "checks": []
    },
    "instruction_specificity": {
      "weight": 15,
      "score": 0,
      "checks": []
    },
    "resource_integration": {
      "weight": 5,
      "score": 0,
      "checks": []
    }
  }
}
```

注意事项：

| 规则 | 说明 |
| --- | --- |
| 分数只进入 supporting evidence | 不直接决定 release。 |
| 分数用于定位弱点 | 例如 frontmatter 弱、checkpoint 弱、资源引用弱。 |
| 分数不可替代 deep eval | 结构分高但回答差，仍应被 deep eval 判为 revise。 |
| 分数不可激励格式堆砌 | 每个检查项要避免奖励冗长规则和机械 checkpoint。 |

Darwin 维度迁移建议：

| Darwin 维度 | Quantitative 检查示例 |
| --- | --- |
| Frontmatter 质量 | `name` 存在、`description` 包含能力与触发场景、长度不过长。 |
| 工作流清晰度 | Step/branch 存在，`direct-result / missing-info / staged` 分支明确。 |
| 边界条件覆盖 | 高压状态、信息不足、越界请求、用户修改路径是否有规则。 |
| 检查点设计 | checkpoint 数量、位置、是否只在 staged 路径出现。 |
| 指令具体性 | 输出 contract、示例、禁止行为、fallback 是否具体。 |
| 资源整合度 | `references/` 链接是否存在，路径是否可读，长材料是否下沉。 |

### 4.3 Deep Quality Rubric

回答的问题：

```text
在真实回答里，skill 是否真正提升用户价值？
```

建议保留当前全局维度，并吸收 Darwin 的 effectiveness 思路，但不采用硬性 25 分主导。

建议 deep eval 输出结构扩展为：

```json
{
  "per_eval": [
    {
      "eval_id": 1,
      "winner": "with_skill",
      "dimension_assessments": [
        {
          "dimension": "User Value",
          "verdict": "strong",
          "evidence_refs": [],
          "notes": "..."
        }
      ],
      "failed_dimensions": [],
      "repair_layer": "skill-content"
    }
  ]
}
```

建议 deep eval 维度：

| 维度 | 判断重点 |
| --- | --- |
| User Value | 是否解决用户任务，而不是展示方法论。 |
| Skill Claim Fit | 输出是否符合该 skill 宣称的独特能力。 |
| Thinking Support | 是否让用户看清结构、取舍、路径。 |
| Judgment Preservation | 是否保留用户判断权，不替用户武断决策。 |
| Protocol Experience | direct-result、missing-info、staged 是否自然，不制造仪式感。 |
| Specificity | 是否贴合用户输入，不泛泛而谈。 |
| Actionability | 是否给出可执行建议、下一步或可用结构。 |
| Boundary Safety | 是否在高压、模糊、越界场景保持安全。 |
| Natural Voice | 是否像一个有帮助的助手，而不是规则说明书。 |
| VisionTree Voice | 是否保持“帮助人更会思考”的立场。 |

其中 Darwin 的“整体结构”和“实测表现”进入 Deep Quality Eval：

| Darwin 项 | Deep Eval 映射 |
| --- | --- |
| 整体结构 | `Skill Claim Fit`、`Protocol Experience`、`Natural Voice` |
| 实测表现 | `User Value`、`Thinking Support`、`Actionability`、`winner` |

## 5. 三层 Rubric 合并机制

建议最终 packet 中使用三层合并：

```json
{
  "rubric": {
    "global": [],
    "package_specific": [],
    "eval_specific": []
  }
}
```

### 5.1 Global Rubric

来源：

```text
toolchain/deep_evals/quality_rubric.py
```

作用：

| 内容 | 是否稳定 |
| --- | --- |
| VisionTree 通用质量标准 | 稳定 |
| 用户价值、思考支持、判断权、边界安全 | 稳定 |
| 自然语气、VisionTree voice | 稳定 |

### 5.2 Package Rubric

建议来源：

```text
packages/<package>/metadata/package.json
packages/<package>/metadata/quality-rubric.json
packages/<package>/references/rubric.md
```

建议第一版用 `metadata/quality-rubric.json`。

示例：

```json
{
  "package_specific": [
    {
      "dimension": "Golden Circle Fit",
      "question": "是否先给价值画面，再自然落到 Why / How / What，而不是提前术语化？"
    }
  ]
}
```

### 5.3 Eval Specific Rubric

来源：

```text
evals/evals.json
```

建议字段：

```json
{
  "quality_rubric": [
    {
      "dimension": "Direct Result Compliance",
      "question": "该 case 信息充分，是否直接给结果而不是 staged checkpoint？"
    }
  ]
}
```

注意：

| 原则 | 说明 |
| --- | --- |
| eval specific rubric 不应太多 | 每条 1 到 3 条即可。 |
| 不替代 expectations | expectations 仍是量化检查，quality_rubric 是质量判断提示。 |
| 不写成答案模板 | 只定义判断标准，不规定固定答案。 |

## 6. 借鉴 Darwin 的流程设计

Darwin 的工程强项是“优化闭环”，不是单次评分。建议将它改造成 `vision-skill` 的迭代纪律。

### 6.1 单一可编辑资产

Darwin 原则：

```text
每次只改一个 SKILL.md
```

在 `vision-skill` 中建议调整为：

```text
每轮只改一个 package 的一个主假设
```

允许改动范围：

| 可改 | 不建议同轮混改 |
| --- | --- |
| `SKILL.md` 核心协议 | eval schema |
| `references/` 示例 | certified eval 扩容 |
| package-specific rubric | runner / judge 逻辑 |

这样能保证失败归因清晰。

### 6.2 独立评分

Darwin 原则：

```text
修改者不能给自己打分
```

当前系统可对应为：

| 角色 | 职责 |
| --- | --- |
| Codex | 总调控、读报告、决定下一轮。 |
| Kimi Production Worker | 生成 eval draft 或 skill rewrite。 |
| Kimi Deep Eval Worker | 读取 run artifacts，生成质量判断。 |
| Human Reviewer | 最终 `pass / revise / hold`。 |

后续建议：

| 改进 | 说明 |
| --- | --- |
| deep eval 使用独立 task dir | 已基本满足。 |
| rewrite worker 不读取 deep eval 输出全文 | 只给 optimization brief，避免过拟合。 |
| reviewer packet 保留代表性原始回答 | 让人工能反查。 |

### 6.3 Ratchet 机制

Darwin 原则：

```text
分数只能上升，退步就 revert。
```

在当前项目中不能简单用总分替代，因为 deep eval 是主判断。建议使用“证据型 ratchet”。

建议新增本地 artifact：

```text
package-workspaces/<package>-workspace/quality-history.json
```

建议字段：

```json
{
  "current_best_iteration": "iteration-3",
  "current_best_summary": {
    "deep_eval_decision": "pass",
    "failed_dimensions": [],
    "quantitative_risks": []
  },
  "attempts": []
}
```

Ratchet 判断建议：

| 条件 | 结果 |
| --- | --- |
| hard gate failed | 不进入候选，不比较质量。 |
| deep eval `hold` | 不采用。 |
| deep eval `revise` 且失败维度未减少 | 不采用。 |
| deep eval `revise` 但失败维度减少且人工认可 | 可进入下一轮候选。 |
| deep eval `pass` 且 human review pass | 更新 current best。 |
| quantitative 风险显著增加 | 标为 risk，不自动否决，但进入人工复核。 |

Git 处理建议：

| 场景 | 建议 |
| --- | --- |
| Kimi worker 产出改动 | Codex review 后 apply。 |
| 改动无效 | 不使用 destructive reset，优先生成反向 patch 或新 commit revert。 |
| 人工要求保留但有风险 | 记录到 `quality-history.json`。 |

### 6.4 测试 prompt 与 certified eval 的关系

Darwin 使用 `test-prompts.json`。当前项目已经有 `eval-factory` 和 certified eval，因此不建议再新增一套并行测试集。

建议映射：

| Darwin | vision-skill |
| --- | --- |
| `test-prompts.json` | `eval-factory/certified-evals/...` |
| 2 到 3 个典型 prompt | certified smoke subset |
| baseline 对照 | `with_skill / without_skill` |
| live performance | deep eval + quantitative differential |

如果要加轻量 prompt，可作为 eval-factory source，不直接散落在 package 内。

## 7. 新流程草案

建议下一版完整流程：

```text
sync certified evals
  -> prepare iteration
  -> execute with_skill / without_skill
  -> hard gate
  -> quantitative bundle
     -> structural diagnostics
     -> benchmark
     -> differential
     -> stability
  -> deep quality eval
     -> global rubric
     -> package rubric
     -> eval rubric
     -> raw run artifacts
  -> optimization brief
  -> Kimi skill rewrite
  -> rerun same eval set
  -> ratchet decision
  -> human review
  -> release recommendation
```

与当前流程相比：

| 当前 | 建议 |
| --- | --- |
| deep eval 有全局 rubric | deep eval 合并 global/package/eval 三层 rubric。 |
| quantitative bundle 包旧指标 | quantitative bundle 增加 Darwin structural diagnostics。 |
| release recommendation 读取 deep eval | release recommendation 增加 ratchet 历史对比。 |
| production cycle 可改 skill | production cycle 每轮绑定一个主失败维度和一个修补假设。 |

## 8. Artifact 变更建议

### 8.1 `hard-gate.json`

第一阶段保持当前结构，只建议补 package gate。

新增字段建议：

```json
{
  "package_gate": {
    "passed": true,
    "blockers": []
  },
  "run_gate": {
    "passed": true,
    "blockers": []
  }
}
```

### 8.2 `quantitative-summary.json`

建议新增：

```json
{
  "structural_diagnostics": {},
  "weighted_structure_score": {
    "score": 0,
    "max_score": 60,
    "role": "diagnostic-only"
  }
}
```

必须保留声明：

```json
{
  "primary_quality_policy": {
    "quality_decision_source": "deep-eval.json",
    "quantitative_role": "supporting diagnostics only"
  }
}
```

### 8.3 `deep-eval.json`

建议新增：

```json
{
  "rubric": {
    "global": [],
    "package_specific": [],
    "eval_specific": []
  },
  "per_eval": [
    {
      "dimension_assessments": [],
      "failed_dimensions": [],
      "repair_hypothesis": ""
    }
  ]
}
```

### 8.4 `optimization-brief.md`

建议新增在 iteration 目录：

```text
iteration-N/optimization-brief.md
```

内容：

| 字段 | 说明 |
| --- | --- |
| 主失败维度 | 来自 deep eval。 |
| 定量支持证据 | 来自 quantitative summary。 |
| 本轮修补假设 | 只允许一个。 |
| 禁止混改项 | 避免同时改 eval、trigger、示例、协议。 |
| 预期改善 | 用可验证语言描述。 |

## 9. 实施路线

### Phase A: Rubric 合并

目标：

```text
deep eval packet 支持 global + package + eval rubric
```

改动：

| 文件 | 改动 |
| --- | --- |
| `toolchain/deep_evals/quality_rubric.py` | 扩展全局 rubric 维度。 |
| `toolchain/deep_evals/packet_builder.py` | 合并 package/eval rubric。 |
| `packages/*/metadata/quality-rubric.json` | 逐步增加 package-specific rubric。 |

验收：

| 标准 | 说明 |
| --- | --- |
| packet 中出现三层 rubric | 必须可测试。 |
| 缺 package rubric 时不报错 | 回退 global。 |
| eval rubric 可选 | 不破坏现有 eval。 |

### Phase B: Darwin Structural Diagnostics

目标：

```text
把 Darwin 可量化结构项迁移到 quantitative bundle
```

改动：

| 文件 | 改动 |
| --- | --- |
| `toolchain/quantitative/skill_structure_score.py` | 新增结构诊断器。 |
| `toolchain/quantitative/run_quantitative_bundle.py` | 写入 `structural_diagnostics`。 |
| `toolchain/quantitative/tests/` | 增加 frontmatter、workflow、resource 测试。 |

验收：

| 标准 | 说明 |
| --- | --- |
| 输出 `weighted_structure_score` | role 必须是 diagnostic-only。 |
| 不影响 deep eval | deep eval 不依赖这个分数。 |
| 不影响旧 artifacts | `benchmark.json` 等继续生成。 |

### Phase C: Optimization Brief

目标：

```text
把 deep eval 的失败维度转成下一轮 Kimi rewrite 的简短任务
```

改动：

| 文件 | 改动 |
| --- | --- |
| `toolchain/deep_evals/` | 增加 brief builder。 |
| `toolchain/kimi_cycle/` | rewrite worker 读取 brief，而不是读取全量 deep eval。 |

验收：

| 标准 | 说明 |
| --- | --- |
| 每轮只有一个主假设 | 降低混改风险。 |
| brief 中文清晰 | 给 Kimi worker 可直接执行。 |
| 引用 evidence refs | 可追溯到原始回答。 |

### Phase D: Ratchet History

目标：

```text
保留最优证据基线，只接受被证明更好的版本
```

改动：

| 文件 | 改动 |
| --- | --- |
| `toolchain/kimi_cycle/` | 增加 quality history 读写。 |
| `package-workspaces/<package>-workspace/quality-history.json` | 记录本地优化历史。 |

验收：

| 标准 | 说明 |
| --- | --- |
| 可比较当前 iteration 和 current best | 不靠口头判断。 |
| 不用 destructive reset | 遵守当前工程安全规则。 |
| 人工可以 override | 但必须记录理由。 |

### Phase E: Review Card

目标：

```text
借鉴 Darwin result card，把评测结果做成更可读的 release packet
```

第一版不需要 PNG。先做 markdown card：

```text
quality-card.md
```

内容：

| 模块 | 来源 |
| --- | --- |
| Deep eval decision | `deep-eval.json` |
| Failed dimensions | `quality-failure-tags.json` |
| Quantitative risks | `quantitative-summary.json` |
| Representative answers | run artifacts |
| Human decision | `human-review-score.json` |

## 10. 不建议照搬的部分

| Darwin 做法 | 不照搬原因 | 替代方案 |
| --- | --- | --- |
| 100 分总分直接比较 | 容易诱导优化分数而不是优化用户价值。 | 分数只做 quantitative diagnostics。 |
| 每个 skill 本地 `test-prompts.json` | 当前已有 eval-factory，重复一套会分叉。 | 把 prompt 进入 certified eval 流程。 |
| 自动 git revert | 当前仓库经常有并行改动，直接 revert 风险高。 | 用 patch/apply、quality history、人审确认。 |
| 结构维度强权重 | Vision skill 更看重回答质量和思考支持。 | 结构项降级为 supporting evidence。 |
| 结果卡优先 | 当前更需要稳定 artifact contract。 | 先做 markdown quality card，PNG 后置。 |

## 11. 推荐下一步

建议按这个顺序做代码改造：

1. 先做 `skill_structure_score.py`，把 Darwin 的 1 到 6 维迁移进 `quantitative-summary.json`。
2. 再做 deep eval 三层 rubric 合并，让 `package_specific` 和 `eval_specific` 能进入 packet。
3. 再做 `optimization-brief.md`，让 Kimi rewrite 每轮只针对一个失败维度。
4. 最后做 ratchet history，把“改了是否更好”变成可追踪的证据基线。

最小可交付版本：

```text
quantitative-summary.json
  + structural_diagnostics

deep-eval.json
  + merged rubric
  + dimension_assessments
  + failed_dimensions

iteration-N/optimization-brief.md
```

这样既吸收 Darwin 的评分纪律，又不破坏当前已经收束好的原则：

```text
Hard Gate 判断是否可评。
Quantitative Bundle 提供可量化诊断。
Deep Eval 做主质量判断。
Human Review 做最终裁决。
Codex 做每一轮总调控。
```
