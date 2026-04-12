# Vision Skill Plan A: Package Factory V0.1

**Project:** `E:\Project\vision-lab\vision-skill`  
**Track:** `Mainline A / Skill Package Factory`  
**Version:** `V0.1`  
**Created:** `2026-03-31`  
**Reference Pattern:** `C:\Users\Administrator\.codex\skills\skill-creator`

---

## 1. Intent

主线 A 的目标不是把 `vision-skill` 做成“更多 markdown”，而是做成一个类似 `skill-creator` 的技能工程系统：

- 每个 Vision skill 都是一个独立 package
- 每个 package 都有标准入口 `SKILL.md`
- 每个 package 都能附带 `references/`、`scripts/`、`assets/`、`evals/`
- 每个 package 都有独立的迭代 workspace
- 每轮修改都能进入评测、对照、报告和回归闭环

这条主线的核心价值是“资产标准化”。先把技能包形态做对，再去追求大规模扩张。

---

## 2. What We Borrow From `skill-creator`

`skill-creator` 给出的不是单一技能写法，而是一套完整技能工程骨架。主线 A 直接吸收以下结构：

### 2.1 Skill Package Anatomy

每个 skill 不是只有 `SKILL.md`，而是一个 package：

```text
skill-name/
  SKILL.md
  evals/
  references/
  scripts/
  assets/
```

### 2.2 Workspace-Based Iteration

每个 skill 都有独立 workspace，保存：

- `iteration-N/`
- 每个 eval 的运行结果
- `history.json`
- `benchmark.json`
- `grading.json`
- `timing.json`

### 2.3 Baseline Comparison

评测不是单看“能不能跑”，而是比较：

- `with_skill`
- `without_skill`
- 后续如有需要，再加 `old_skill`

### 2.4 Lightweight Validation

技能包必须先通过快速校验，再进入深入评测。主线 A 需要类 `quick_validate.py` 的本地快速校验器。

### 2.5 Iterative Improvement Loop

标准闭环是：

`draft -> test prompts -> run -> grade -> benchmark -> review -> improve -> rerun`

Vision skill 的第一版工程也按这个闭环组织。

---

## 3. Core Design Decision

主线 A 采用以下核心判断：

### 3.1 Package Over Monolith

不再把 135 个 demo 看成一个大资料堆，而是拆成多个标准 package。

### 3.2 Package Over Raw Markdown

最终产物虽然仍是 `SKILL.md`，但真实工程对象是 package，而不是孤立 markdown。

### 3.3 Eval-Ready By Default

所有正式 package 默认必须带 `evals/`，而不是事后补测试。

### 3.4 Workspace Is Mandatory

技能改进过程不得散落在聊天记录里；每个 skill 必须有自己的 workspace 和历史记录。

### 3.5 Package Is Internal Product Unit

对外不宣传“skill 工厂”，但对内每个 package 就是一个最小产品单元。

---

## 4. Proposed Repository Structure

主线 A 建议把仓库扩展为如下结构：

```text
vision-skill/
  docs/
    project-plans/
    package-specs/
  packages/
    growth-breakthrough/
      SKILL.md
      evals/
        evals.json
      references/
      scripts/
      assets/
      metadata/
        package.json
        source-map.json
    swot-analysis/
    first-principles/
    ...
  package-workspaces/
    growth-breakthrough-workspace/
      history.json
      iteration-1/
      iteration-2/
    swot-analysis-workspace/
  shared/
    source-index/
    glossaries/
    boundary-rules/
    review-templates/
  toolchain/
    validators/
    builders/
    graders/
    benchmarks/
    packagers/
  reports/
    audits/
    benchmarks/
    release/
```

职责划分：

- `packages/`
  - 正式 skill package 目录
- `package-workspaces/`
  - 每个 package 的迭代轨迹和 benchmark 历史
- `shared/`
  - 跨 package 共用的知识与规则
- `toolchain/`
  - build、validate、grade、aggregate、report 工具
- `reports/`
  - 面向项目管理和发布决策的报告层

---

## 5. Package Contract

每个 Vision skill package 必须满足以下契约。

### 5.1 Required Files

```text
<package>/
  SKILL.md
  evals/evals.json
  metadata/package.json
  metadata/source-map.json
```

### 5.2 Optional Files

```text
references/
scripts/
assets/
metadata/style-profile.json
metadata/release-notes.md
```

### 5.3 `SKILL.md` Role

负责：

- frontmatter
- 触发描述
- 主体工作流
- 输出格式
- 边界规则
- 引导读取 `references/` 和调用 `scripts/`

不负责：

- 承载所有来源知识全文
- 承载所有测试样例
- 承载全部版本历史

### 5.4 `evals/evals.json` Role

负责定义：

- eval id
- prompt
- expected output
- input files
- expectations

这是 package 的正式测试入口。

### 5.5 `metadata/package.json` Role

建议字段：

- `package_name`
- `skill_name`
- `category`
- `status`
- `version`
- `owner`
- `core_track`
- `release_stage`

### 5.6 `metadata/source-map.json` Role

负责保存：

- source ids
- 关键依据摘要
- 冲突说明
- 当前 package 对应的 demo 迁移来源

---

## 6. Workspace Contract

每个正式 package 都必须有一个独立 workspace。

### 6.1 Workspace Layout

```text
<package>-workspace/
  history.json
  iteration-1/
    eval-0/
      with_skill/
      without_skill/
    benchmark.json
    benchmark.md
  iteration-2/
```

### 6.2 `history.json`

记录：

- 开始时间
- 当前最佳版本
- 每轮 pass rate
- 每轮比较结果

### 6.3 Iteration Directory

每轮至少保存：

- 原始输出
- transcript
- grading
- timing
- metrics
- benchmark

### 6.4 Why Workspace Matters

主线 A 规定：

- 不允许只有“最终文件”，没有中间记录
- 不允许只看主观印象，不留 benchmark
- 不允许无法回答“这个 skill 是怎么变好的”

---

## 7. Build and Release Loop

主线 A 的 package 生命周期：

### Stage 1: Candidate

来源：

- 现有 demo skill
- 现有 demo skill 的直接迁移与整理
- 现有 demo skill 的结构重组、补元数据与补评测

产出：

- package 目录壳
- draft `SKILL.md`
- 初版 `evals.json`

说明：

- 主线 A 的 Candidate 阶段暂不从 `vision-doc` 或 `skill-doc` 直接生 skill。
- `vision-doc` 与 `skill-doc` 仍作为校准和后续增强依据，但首轮 candidate 只从 demo 出发。

### Stage 2: Validated Candidate

要求：

- 通过 package 结构校验
- 通过 `SKILL.md` frontmatter 校验
- 通过基础静态规则

### Stage 3: Benchmarked Package

要求：

- 已完成至少一轮 with-skill / without-skill 对照
- 已生成 `grading.json`
- 已生成 `benchmark.json`
- 已形成第一轮 review notes

### Stage 4: Core Package

要求：

- 通过核心 capability eval
- 回归集完整
- 人审通过
- 纳入 core-20

### Stage 5: Release Package

要求：

- 版本稳定
- 文档齐全
- 有 release notes
- 满足后续平台适配前置条件

---

## 8. Evaluation System For Mainline A

主线 A 的评测要尽量贴近 `skill-creator` 的评测节奏，但做 Vision 场景适配。

### 8.1 Static Validation

至少包括：

- package 必需文件存在
- `SKILL.md` frontmatter 正确
- 章节结构完整
- 不含旧路径 `/home/pc/...`
- 不含违背 VisionTree 的禁用表述
- `evals/evals.json` 符合 schema

### 8.2 Capability Evals

用于判断 skill 在核心任务上是否有价值。

Vision skill 必须覆盖：

- 信息不足时只补问缺失项
- 信息充分时不重复提问
- `继续` / `不对` / `直接要结果`
- 高压状态减压优先
- 输出结构完整且不泛化

### 8.3 Regression Evals

所有修复过的问题必须进入回归集。

### 8.4 Benchmarking

主线 A 默认保留：

- pass rate
- time
- tokens
- tool calls
- error count

### 8.5 Human Review

对于 Vision skill，人工复核重点高于多数通用工具 skill：

- 是否保持“帮助人更会思考”
- 是否避免替代思考
- 是否有真实判断节点
- 是否有明显鸡汤化、心理按摩化、平均化回答

---

## 9. Toolchain Scope

主线 A 需要在 `toolchain/` 里形成一组本地工具。

### 9.1 Validators

参考 `skill-creator/scripts/quick_validate.py`，实现：

- package structure validate
- frontmatter validate
- eval schema validate

### 9.2 Builders

负责：

- 从 brief / blueprint 生成 package
- 写入 `metadata/`
- 渲染 `SKILL.md`

### 9.3 Graders

负责：

- 将 expectations 映射成 grading 结果
- 生成 `grading.json`

### 9.4 Benchmarks

负责：

- 聚合 iteration 下所有 run
- 生成 `benchmark.json` 和 `benchmark.md`

### 9.5 Packagers

负责：

- 后续把正式 package 打成可分发产物

---

## 10. Core-20 Rollout Under Mainline A

主线 A 不直接把 135 个 demo 全部 package 化。

### Batch 1

先选 5 个 package 做模板验证：

- 个人成长类 1 个
- 问题解决类 2 个
- 商业战略类 1 个
- 情绪/高风险类 1 个

### Batch 2

扩展到 20 个 core packages。

### Batch 3

只有在：

- package 结构稳定
- eval schema 稳定
- benchmark 管线稳定

之后，才考虑继续扩到 135 个。

---

## 11. Phase Plan

### Phase A1: Package Spec

输出：

- package anatomy 规范
- workspace anatomy 规范
- package metadata 规范
- eval schema 规范

### Phase A2: Toolchain Bootstrap

输出：

- quick validator
- package scaffold builder
- eval scaffold builder
- benchmark aggregator

### Phase A3: First 5 Packages

输出：

- 5 个标准 package
- 对应 workspace
- 首轮 benchmark
- 首轮人审意见

### Phase A4: Core-20

输出：

- 20 个 core packages
- history 与 benchmark 完整沉淀
- release candidate 清单

---

## 12. Acceptance Criteria

主线 A 的第一阶段完成标准：

- 所有 core package 都具备标准目录结构
- 所有 core package 都有 `evals/evals.json`
- 所有 core package 都有独立 workspace
- 所有 core package 都至少完成一轮 benchmark
- 核心协议回归通过率 100%
- 能力评测通过率 >= 85%
- 人审完成率 100%

---

## 13. Why Mainline A Is Different From V0.1

相比通用版 V0.1，主线 A 的差异在于：

- 更强调“每个 skill 是 package”
- 更强调“每个 skill 都有 workspace”
- 更强调“benchmark 和 history 是正式资产”
- 更贴近 `skill-creator` 的工程结构，而不是抽象的 pipeline 语言

V0.1 更像总纲；主线 A 更像可以直接开始搭骨架的项目蓝图。

---

## 14. Immediate Next Actions

主线 A 建议立刻推进：

1. 新建 `packages/`、`package-workspaces/`、`toolchain/` 目录。
2. 定义 package 最小规范。
3. 定义 `evals/evals.json` 的 Vision 版本 schema。
4. 先把 1 个 demo skill 迁成标准 package。
5. 跑通第一轮 validate + benchmark。

---

## 15. Revision Log

- `2026-03-31 / V0.1`
  - 基于 `skill-creator` 结构细化主线 A
  - 明确 package、workspace、benchmark、history 为主线 A 的四个关键工程对象
- `2026-04-08 / V0.1 minor`
  - 将 `Stage 1: Candidate` 的来源收紧为 demo-only
  - 与当前仓库的实际迁移路径保持一致
