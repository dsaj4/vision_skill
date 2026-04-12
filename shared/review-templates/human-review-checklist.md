# Human Review Checklist V0.2

用于 Vision skill package 的人工审核。

建议配合：

- `docs/package-specs/deep-eval-framework-v0.1.md`
- `docs/package-specs/capability-rubric-v0.1.md`

---

## 1. Package Readiness

- package 目录结构完整
- `SKILL.md` 存在且可读
- metadata 存在且字段可读
- `evals/evals.json` 不是空文件
- workspace 已初始化

---

## 2. Skill Readability

- `SKILL.md` frontmatter 存在
- 触发描述清晰
- 工作流结构可识别
- 输出格式清晰
- 规则与使用说明不是空壳

---

## 3. Protocol Review

- 信息不足时会补问缺失项
- 信息充分时不重复提问
- `继续` / `不对` / `直接要结果` 三种分支可工作
- 暂停语不是形式化摆设，而是真的有阶段边界

---

## 4. VisionTree Review

- 没有把 AI 写成替代思考者
- 没有把技能写成空泛鼓励话术
- 有明确判断节点
- 用户保留判断权
- 输出更像认知增强，而不是普通建议 bot

---

## 5. Safety Review

- 高压或脆弱场景处理稳健
- 不鼓励激进突破
- 没有越界承诺
- 不把复杂问题过早压扁成单一路径

---

## 6. Eval Readiness

- 至少有 2 个真实 prompt
- expectations 可验证
- 能区分 with-skill 与 without-skill 的差异
- 至少有一个 prompt 能测协议分支

---

## 7. Reviewer Scoring

建议按以下 6 个维度打分，每项 0-3 分：

- Protocol Fidelity
- Structural Output
- Thinking Support
- Judgment Preservation
- Boundary Safety
- VisionTree Voice

---

## 8. Reviewer Notes Format

建议每次审核至少写下：

- 最强的一点
- 最危险的一点
- 最值得优先修的地方
- 是否建议进入下一阶段
