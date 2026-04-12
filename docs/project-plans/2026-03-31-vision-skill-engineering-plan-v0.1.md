# Vision Skill Engineering Plan V0.1

**Project:** `E:\Project\vision-lab\vision-skill`  
**Version:** `V0.1`  
**Status:** `Draft / Executable Planning Baseline`  
**Created:** `2026-03-31`  
**Primary Sources:** `E:\Project\vision-lab\vision-doc`, `E:\Project\vision-lab\skill-doc`

---

## 1. Planning Intent

本文件用于把当前 `vision-skill` 从“思维模型 demo 资产包”升级为“可持续构建、可评测、可迭代、可扩批”的工程项目。

第一阶段不追求一次性重做全部 135 个 demo skill，而是先建立一条稳定主线：

`source material -> blueprint -> build -> static eval -> behavior eval -> human review -> iteration report`

第一阶段的正式交付格式仍然是 `SKILL.md`，但 `SKILL.md` 不再是唯一真相。正式真相上移到 source index、blueprint 和评测资产。

---

## 2. Current State

当前目录主要由以下内容组成：

- `思维模型/思维模型`
  - 现有 demo 资产主体
  - 含多类 `SKILL.md`
  - 含一次性脚本和抽样测试报告
- `思维模型.zip`
  - demo 压缩包备份

当前问题：

- 现有 skill 以最终文档为中心，缺少上游结构化规格。
- 批量更新脚本仍带有旧环境路径和一次性迁移痕迹。
- 抽样测试主要是静态检查，尚未形成标准化行为评测与回归机制。
- `vision-doc` / `skill-doc` 的知识尚未进入可重复消费的工程输入层。
- 缺少正式的规划目录、规范文档、数据模型说明和版本迭代机制。

---

## 3. Phase-1 Goal

第一阶段目标是建立 `ADLC + 模块化评测` 的本地工程主线，并在该主线上形成首批 20 个核心 skill 黄金集的交付能力。

第一阶段必须完成：

- 建立 source of truth 目录与索引。
- 建立 canonical skill blueprint 规范。
- 建立本地 build pipeline。
- 建立静态评测、行为评测、人审抽检三层闭环。
- 建立 failure taxonomy 与回归集机制。
- 建立首批 20 个核心 skill 的候选清单与产出路径。

第一阶段明确不做：

- 不以 Coze、PoE、ChatGPT Store 的上线适配为主线。
- 不依赖外部评测 SaaS 作为首期必需能力。
- 不把“skill 平台”作为对外产品叙事。
- 不直接用人工逐个散改方式维护 135 个 skill。

---

## 4. Working Principles

### 4.1 Source Priority

- `vision-doc` 与 `skill-doc` 是正式知识源。
- 现有 135 个 demo skill 是迁移样本、结构样本、风险样本。
- 文档与 demo 冲突时，默认文档优先，并记录冲突。

### 4.2 Build Priority

- 所有正式 skill 先有 blueprint，再生成 `SKILL.md`。
- 不允许长期直接手改最终 `SKILL.md` 作为主要维护方式。
- 若 `SKILL.md` 有问题，优先回到 source、blueprint、template 或 eval 规则层修复。

### 4.3 Eval Priority

- 没有通过评测的 skill，不视为正式产物。
- 回归集优先于新增覆盖面。
- 失败必须带归因标签，不能只写“待优化”。

### 4.4 VisionTree Boundary

- 对内可使用 skill 工程、评测、流水线等术语。
- 对外叙事仍保持 VisionTree 的“用 AI 给人做技能”“帮助人更会思考”立场。
- 工程过程不得把内容写成通用鸡汤、替代思考型 AI、纯模型库宣传。

---

## 5. Proposed Repository Expansion

第一阶段建议在 `vision-skill` 下增加以下结构：

```text
docs/
  project-plans/
  specs/
sources/
  source-index/
  glossaries/
  boundary-rules/
  source-maps/
blueprints/
  schemas/
  draft/
  core-20/
pipeline/
  builders/
  renderers/
  critics/
  manifests/
evals/
  static/
  behavior/
  human-review/
  datasets/
reports/
  audits/
  evals/
  iterations/
artifacts/
  generated-skills/
```

目录职责：

- `docs/project-plans/`
  - 规划文档版本库
- `docs/specs/`
  - 后续 blueprint 规范、字段说明、渲染契约
- `sources/`
  - Source index、术语表、边界规则、来源映射
- `blueprints/`
  - 每个 skill 的结构化规格
- `pipeline/`
  - 构建、渲染、批判重写、manifest 生成脚本
- `evals/`
  - 静态评测规则、行为评测用例、人审模板、回归集
- `reports/`
  - demo 审计、评测报告、迭代报告
- `artifacts/generated-skills/`
  - 由 pipeline 输出的正式 `SKILL.md` 产物

---

## 6. Phase-1 Data Contracts

### 6.1 Source Index

需要建立统一的 source index，至少记录：

- `source_id`
- `title`
- `path`
- `source_type`
- `trust_level`
- `topic_tags`
- `intended_usage`
- `notes`

目标：

- 给每份文档一个稳定 id。
- 让后续 blueprint 可以引用具体来源，而不是靠人工描述。

### 6.2 Skill Blueprint

每个 skill blueprint 至少包含：

- `metadata`
  - 名称、类别、适用场景、触发描述
- `source_refs`
  - 来源文档 id 与关键依据摘要
- `input_requirements`
  - Step 0 信息完整度判断逻辑
- `interaction_protocol`
  - 分步执行、暂停确认、跳过机制、修改重做
- `output_contract`
  - 输出结构、表格、行动建议、提醒项
- `guardrails`
  - 高压状态、越界请求、模糊问题处理
- `style_profile`
  - VisionTree 立场、禁用表达、专业深度、语气约束
- `eval_refs`
  - 静态规则 id、行为用例 id、人审项 id

### 6.3 Build Manifest

每次构建都必须生成 manifest，至少记录：

- `build_id`
- `skill_id`
- `blueprint_version`
- `template_version`
- `source_snapshot`
- `artifact_path`
- `review_note_path`
- `created_at`

### 6.4 Eval Case

行为评测用例至少包含：

- `case_id`
- `skill_id`
- `eval_type`
- `input_messages`
- `expected_checks`
- `grader_type`
- `failure_tags`

---

## 7. Build Pipeline V1

第一阶段构建链路定义如下：

### Step 1: Source Parsing

从 `vision-doc` 和 `skill-doc` 提取结构化 brief：

- 主题
- 核心任务
- 适用边界
- 交互逻辑
- 风格信号
- 风险限制

### Step 2: Blueprint Assembly

将 brief 转换成统一 blueprint，补齐规范字段，形成后续唯一设计入口。

### Step 3: Draft Generation

基于模板生成第一版 skill 草案。

### Step 4: Critic / Rewrite

在构建阶段引入一轮轻量质量门：

- critic 检查逻辑空泛
- critic 检查风格漂移
- critic 检查边界模糊
- rewrite 根据 critic 结果重写

### Step 5: Template Rendering

将重写后的结构化内容渲染成正式 `SKILL.md`。

### Step 6: Artifact Registration

为每次构建输出：

- `SKILL.md`
- `build_manifest.json`
- `source_trace.json`
- `draft_review_notes.md`

### Step 7: Evaluation Entry

构建完成后必须进入评测，不允许构建即视为完成。

---

## 8. Evaluation Architecture V1

### 8.1 Static Eval

静态评测负责检查结构和规则一致性，至少覆盖：

- frontmatter 完整性
- `## 交互模式`
- `Step 0`
- Step 1-3 暂停语
- `## 规则`
- `## 使用说明`
- blueprint 字段映射完整性
- 禁用旧环境路径
- 禁用明显越界和替代思考型表达

### 8.2 Behavior Eval

行为评测负责回放关键交互分支，至少覆盖：

- 信息不足时只追问缺失项
- 信息充分时直接分析
- 用户回复 `继续`
- 用户回复 `不对 + 修改意见`
- 用户回复 `直接要结果`
- 高压与脆弱状态优先减压
- 越界请求时触发边界规则

行为评测需要沉淀：

- `transcript`
- `trace`
- `outcome`
- `grader_result`
- `failure_tags`

### 8.3 Human Review

第一轮对 20 个核心 skill 全量人工审核。

人审重点：

- 是否保持 VisionTree 立场
- 是否避免替代思考叙事
- 是否具备真实交互自然性
- 是否在高风险场景下处理稳健
- 是否存在内容空泛、鸡汤化、平均化回答倾向

---

## 9. Iteration Loop

所有失败只允许归因到以下四类：

- `source`
- `blueprint/spec`
- `template`
- `skill-content`

每轮迭代必须输出结构化报告，至少包含：

- 新增失败项
- 已修复项
- 回归结果
- 当前遗留风险
- 下一轮优先级建议

回归机制：

- 修过的问题必须进入回归集。
- 新模板上线前必须重跑核心回归集。
- 首批 20 个核心 skill 是黄金基线，后续扩批必须先对齐这套基线。

---

## 10. Core-20 Strategy

第一阶段先做 20 个核心 skill，而不是全量 135 个。

选择原则：

- 覆盖现有主要类别
- 覆盖最能体现“节点断点式交互”的 skill
- 覆盖风险边界敏感的 skill
- 覆盖结构较复杂、最能暴露模板和评测问题的 skill

首批 20 个核心 skill 候选名单不在本文件硬编码，后续作为 Phase 1 产出单独维护，以便替换和扩充。

---

## 11. Phase Deliverables

### Phase 1: 工程地基

输出：

- 规划目录和规划文档
- source index 草案
- 术语表与边界规则表
- blueprint schema 草案
- build manifest 结构说明
- eval case 结构说明
- demo 审计清单
- core-20 候选名单

### Phase 2: 构建链路

输出：

- 可重复运行的本地 build pipeline
- 3-5 个样板 skill
- 对应 manifest、trace、review notes

### Phase 3: 评测链路

输出：

- static eval runner
- behavior eval runner
- human review checklist
- 第一版 capability / regression 数据集

### Phase 4: 黄金集产出

输出：

- 20 个核心 skill 黄金集
- 第一版回归集
- iteration report v1

---

## 12. Acceptance Baseline

第一阶段验收以以下基线为准：

- 20 个核心 skill 的协议型回归用例通过率 100%
- 20 个核心 skill 的能力评测通过率 >= 85%
- 所有失败项均有归因标签与修复建议
- 第一轮人审覆盖 20 个核心 skill 全量
- 每一轮迭代都有结构化报告沉淀

---

## 13. Immediate Next Actions

建议按以下顺序继续推进：

1. 在 `sources/` 下建立 source index、术语表、边界规则表。
2. 在 `blueprints/schemas/` 下定义首版 blueprint schema。
3. 对现有 demo skill 做一次结构审计，产出迁移清单。
4. 选出 20 个核心 skill 候选并建立空 blueprint。
5. 先打通 1 个样板 skill 的 build + static eval。

---

## 14. Revision Policy

本文件为 `V0.1` 基线版本。

后续更新规则：

- 大改动：新增 `V0.2`、`V0.3` 等新文档版本
- 小修订：在本文件末尾追加修订记录

### Revision Log

- `2026-03-31 / V0.1`
  - 新建规划目录
  - 落成第一版实际项目规划文档
  - 确立 Phase-1 的 ADLC 与模块化评测主线
