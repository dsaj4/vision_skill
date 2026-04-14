# Vision Skill Project Plans

该目录用于沉淀 `vision-skill` 的工程规划、阶段说明与后续版本更新。

当前文件：

- `2026-03-31-vision-skill-engineering-plan-v0.1.md`
  - 第一版实际项目规划文档
  - 用于指导 `vision-skill` 从 demo 资产升级为可持续的构建、评测、迭代工程
- `2026-03-31-vision-skill-plan-a-package-factory-v0.1.md`
  - 主线 A 细化版规划文档
  - 参考 `skill-creator` 的技能包、评测、workspace、benchmark 结构
  - 用于把 `vision-skill` 组织成可扩展的 skill package factory
- `2026-04-13-vision-skill-eval-effectiveness-suite-design-v0.1.md`
  - 第一版严格效果区分测试套件设计
  - 用于验证当前评测系统是否具备基本区分力
- `2026-04-13-vision-skill-differential-eval-and-eval-factory-design-v0.1.md`
  - 第一版差异评测与轻量评测集工厂设计
  - 用于定义 Level 3 主评分替换方向和高质量 eval 的生成路径

约定：

- 每次大版本更新新增一个带日期和版本号的规划文档，不覆盖旧版本。
- 同一版本内的小修订直接在文档内追加修订记录。
- 规划文档是实现与评测工作的上游依据，不直接替代 blueprint、eval case 或 build manifest。
