# Vision Deep Eval Framework V0.1

**Scope:** `Mainline A / Skill Package Factory`  
**Applies To:** candidate packages, core packages, release packages

---

## 1. Intent

这个框架用于回答 4 个问题：

1. 这个 package 结构上是否合格
2. 这个 skill 是否按设计协议运行
3. 这个 skill 相比 baseline 是否真的更有价值
4. 这个 skill 是否稳定、可解释、且符合 VisionTree 的认知立场

因此评测不能只停留在“能不能跑”，而要分层推进到深度评测。

---

## 2. Evaluation Stack

主线 A 的评测分为 6 层。

### Level 1: Structural Validation

目标：

- 判断 package 是否具备最小工程形态

检查对象：

- package 必需目录和文件
- `SKILL.md` frontmatter
- `metadata/package.json`
- `metadata/source-map.json`
- `evals/evals.json`

典型输出：

- `validate-report.json`

通过条件：

- 必需文件齐全
- JSON 可解析
- 不存在明显格式错误

### Level 2: Protocol Validation

目标：

- 判断 skill 是否遵守自己的交互协议

关键场景：

- 信息不足时只补问缺失项
- 信息充分时不重复提问
- `继续`
- `不对 + 修改意见`
- `直接要结果`
- 高压状态时先减压

典型输出：

- `protocol-grading.json`

通过条件：

- 核心协议 expectation 通过率必须为 100%

### Level 3: Value Evaluation

目标：

- 判断 `with_skill` 是否比 `without_skill` 更有价值

比较方式：

- 对同一组 prompt 同时保留：
  - `with_skill`
  - `without_skill`

重点比较：

- 结构化程度
- 跑偏率
- 风格一致性
- 风险边界处理
- 是否更像“帮助思考”而非“替你判断”

典型输出：

- `grading.json`
- `benchmark.json`

通过条件：

- `with_skill` 在关键 expectation 上优于 `without_skill`

### Level 4: Stability Evaluation

目标：

- 判断 skill 是否稳定，而不是偶然答对一次

方法：

- 同一个 eval 至少跑 2-3 次
- 观察：
  - pass rate mean
  - 方差
  - 易波动 expectation
  - 高风险输入下是否失控

重点输入类型：

- 模糊输入
- 长输入
- 情绪化输入
- 混合诉求输入
- 中途修改输入

典型输出：

- `benchmark.json`
- `benchmark-notes.md`

通过条件：

- 高优先级 expectation 不出现明显随机漂移

### Level 5: Mechanism Evaluation

目标：

- 判断 skill 的 instruction 是否真的被使用
- 找出“为什么好”或“为什么坏”

分析对象：

- transcript
- trace
- timing
- metrics
- grader evidence

重点问题：

- 模型有没有按 skill 结构走
- 哪些 instruction 没有被采纳
- 哪些 instruction 在浪费 token
- 失败是内容问题，还是 skill 结构问题

典型输出：

- `analysis.md`
- `analysis.json`

通过条件：

- 主要失败原因可归因，不进入“说不清为什么坏”的状态

### Level 6: Cognitive Evaluation

目标：

- 判断 skill 是否真正符合 VisionTree 的产品哲学

核心维度：

- 是否帮助用户更会思考
- 是否保留判断权
- 是否有真实节点断点
- 是否避免鸡汤化与替代思考
- 是否在高压状态下稳健

典型输出：

- `human-review.md`
- `human-review-score.json`

通过条件：

- 人审 rubric 达到最低门槛

---

## 3. Baseline Policy

当前阶段默认 baseline 为：

- `without_skill`

后续在 package 进入改进模式后，可增加：

- `old_skill`

使用规则：

- 新 package：必须至少对比 `with_skill` vs `without_skill`
- 已有 package 改版：建议同时保留 `old_skill`

---

## 4. Eval Types

每个 package 的评测集拆成两大类。

### Capability Evals

作用：

- 判断 skill 是否具备核心能力

特点：

- 覆盖主要交互能力
- 重点看“有没有价值”
- 允许暴露边缘失败

### Regression Evals

作用：

- 防止已修复问题重新出现

特点：

- 来自历史失败样本
- 数量可以逐步增加
- 核心协议相关项必须保持 100% 通过

---

## 5. Standard Eval Artifacts

每轮评测至少沉淀这些资产：

- `evals/evals.json`
- `timing.json`
- `metrics.json`
- `grading.json`
- `benchmark.json`
- `benchmark.md`
- `analysis.md` 或 `analysis.json`
- `human-review.md`

如果暂时还没有自动化 runner，也要先按文件位点和命名习惯沉淀下来。

---

## 6. Suggested Gating Rules

### Candidate -> Validated Candidate

要求：

- Level 1 通过
- Level 2 基本通过

### Validated Candidate -> Benchmarked Package

要求：

- 完成一轮 `with_skill` / `without_skill`
- 生成 `grading.json`
- 生成 `benchmark.json`

### Benchmarked Package -> Core Package

要求：

- 协议回归 100%
- capability pass rate >= 85%
- 关键人审维度全部过线

### Core Package -> Release Package

要求：

- 稳定性通过
- 主要失败已归因
- 有明确 release notes

---

## 7. Deep Eval Signals

除了基础测试，进入深度评测时要重点看以下信号。

### 7.1 Value Signal

- `with_skill` 是否明显优于 baseline

### 7.2 Variance Signal

- 同一 prompt 多次运行是否波动剧烈

### 7.3 Drift Signal

- 输出是否逐渐滑向泛化回答、鸡汤、替代思考

### 7.4 Cost Signal

- 时间、token、tool calls 是否过重

### 7.5 Mechanism Signal

- instruction 是否在 transcript 中真的起作用

### 7.6 Philosophy Signal

- 是否仍是 VisionTree 的 skill，而不是普通建议型 bot

---

## 8. What Deep Eval Is For

深度评测不是为了制造复杂度，而是为了支持 3 个决策：

- 这个 package 值不值得继续做
- 下一轮应该改什么，而不是瞎调 prompt
- 这个 package 能不能进入 core-20

---

## 9. Immediate Adoption

当前建议立刻采用：

1. 每个 package 先补齐 Level 1 与 Level 2 所需资产
2. core candidate 补 `with_skill` / `without_skill` 对照
3. 人审开始使用统一 rubric
4. 所有失败统一进入 failure taxonomy
