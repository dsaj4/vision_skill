# Vision Skill Mainline A System Overview V0.1

**Project:** `E:\Project\vision-lab\vision-skill`  
**Track:** `Mainline A / Package Factory`  
**Purpose:** 帮助从整体架构理解当前主线，而不是只看单个模块

---

## 1. What This Document Is For

这份文档不是某一个模块的局部说明，而是主线 A 的总规划图。

目标：

- 看清整个系统如何从 demo 出发
- 看清 package、workspace、eval、iteration 之间的关系
- 看清我们当前已经搭好的骨架在整个架构里的位置

---

## 2. Mainline A In One Sentence

主线 A 要把现有 demo skill 迁移成标准 package，再通过 build、eval、review、iteration 的闭环，把其中一部分筛选和提升为 core packages。

---

## 3. System Modules

主线 A 当前可以拆成 7 个模块。

### Module 1: Demo Source Layer

当前候选来源只来自 demo。

职责：

- 提供 candidate seed
- 提供旧 skill 文本
- 提供迁移样本和风险样本

当前对应目录：

- `思维模型/思维模型`
- `shared/source-index/`

### Module 2: Package Layer

这是主线 A 的核心生产单元。

职责：

- 把 skill 组织成标准 package
- 承载 `SKILL.md`、`evals/`、`metadata/`
- 作为后续 build、eval、release 的最小对象

当前对应目录：

- `packages/`

### Module 3: Shared Rules Layer

这是所有 package 共用的规则层。

职责：

- 统一 source index
- 统一边界规则
- 统一 review 模板
- 后续沉淀术语表

当前对应目录：

- `shared/`

### Module 4: Toolchain Layer

这是所有工程自动化能力的集合。

职责：

- validate
- build
- grade
- benchmark
- package

当前对应目录：

- `toolchain/`

### Module 5: Eval Layer

这是整个系统的质量门。

职责：

- 先做基础测试
- 再进入深度评测
- 决定 package 能否升级阶段

当前对应目录：

- `packages/<package>/evals/`
- `docs/package-specs/deep-eval-framework-v0.1.md`
- `shared/review-templates/`

### Module 6: Workspace Layer

这是每个 package 的历史与证据层。

职责：

- 保存 iteration
- 保存 benchmark
- 保存 grading
- 保存历史最佳版本

当前对应目录：

- `package-workspaces/`

### Module 7: Reports Layer

这是面向项目视角的输出层。

职责：

- 审计
- benchmark 汇总
- release candidate 说明

当前对应目录：

- `reports/`

---

## 4. End-to-End Workflow

主线 A 的整体流程如下：

```text
demo source
  -> candidate package
  -> structure validation
  -> protocol validation
  -> capability eval
  -> benchmark against baseline
  -> human review
  -> failure taxonomy
  -> iteration workspace update
  -> stage promotion decision
```

换成工程对象视角：

```text
demo skill
  -> package/
  -> evals/
  -> toolchain/
  -> package-workspace/
  -> reports/
```

---

## 5. Where Eval Sits In The System

eval 不是尾部补充，而是中间质量门模块。

它插在这个位置：

```text
candidate package
  -> validate
  -> eval
  -> review
  -> iterate
  -> promote or hold
```

它的作用不是“看看表现”，而是负责 3 个判断：

1. 这个 package 现在能不能继续往前走
2. 这个 package 下一轮该改哪里
3. 这个 package 最终能不能进 core-20

所以 eval 模块和 package、workspace、reports 是强耦合关系。

---

## 6. Eval As A Module

当前 eval 模块由 4 个层面组成：

### A. Eval Inputs

- `evals/evals.json`
- baseline policy
- capability rubric
- human review checklist

### B. Eval Execution

- static validation
- protocol validation
- capability eval
- stability eval
- mechanism analysis
- cognitive review

### C. Eval Outputs

- `grading.json`
- `benchmark.json`
- `benchmark.md`
- `analysis.md`
- `human-review.md`

### D. Eval Decisions

- hold
- revise
- benchmark again
- promote stage

---

## 7. Stage Model

主线 A 当前建议的阶段模型：

### Stage 1: Candidate

- 来源只允许来自 demo
- 目标是完成 package 化

### Stage 2: Validated Candidate

- 通过结构和协议检查

### Stage 3: Benchmarked Package

- 已有 with-skill / without-skill 对照
- 有 benchmark 证据

### Stage 4: Core Package

- 达到能力门槛
- 达到人审门槛
- 纳入 core-20

### Stage 5: Release Package

- 稳定、可解释、可记录
- 适合进入下一阶段的分发或平台适配

---

## 8. Current Repository Mapping

到今天为止，主线 A 已经有这些落点：

- 规划文档
  - `docs/project-plans/`
- package 规范
  - `docs/package-specs/`
- 首个候选包
  - `packages/swot-analysis/`
- 首个 workspace
  - `package-workspaces/swot-analysis-workspace/`
- shared 基础目录
  - `shared/`
- toolchain 基础目录
  - `toolchain/`
- reports 基础目录
  - `reports/`

这意味着我们已经从“想法”进入“系统骨架已存在”的阶段。

---

## 9. How To Read The Whole Architecture

如果从整体理解，建议按这个顺序看：

1. 看 `docs/project-plans/`
   - 理解主线和阶段目标
2. 看 `docs/package-specs/`
   - 理解 package 和 eval 契约
3. 看 `packages/swot-analysis/`
   - 理解最小 package 长什么样
4. 看 `package-workspaces/swot-analysis-workspace/`
   - 理解迭代证据怎么保存
5. 看 `shared/` 与 `toolchain/`
   - 理解共用层和自动化层预留了什么

---

## 10. Immediate Next Steps

从系统层面，下一步最顺的是：

1. 在 `toolchain/validators/` 落第一个真实 validator
2. 把 `swot-analysis` 跑完第一轮 static/protocol eval
3. 再迁 1-2 个 demo package
4. 开始形成第一版 cross-package benchmark 视角

---

## 11. Summary

如果把主线 A 看成一条完整生产线：

- demo 是原料
- package 是标准件
- eval 是质量门
- workspace 是证据库
- reports 是管理层视图

这样理解，整个架构会比较稳，也方便后面继续扩批而不失控。
