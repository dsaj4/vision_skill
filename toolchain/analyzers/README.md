# Analyzers

这里放 Level 5 机制分析模块。

当前第一版：
- 读取 benchmark、stability、run artifacts 和 `SKILL.md`
- 生成 analyzer packet
- 调用 DashScope 兼容接口做模型主导分析
- 写入 `analysis.json`、`analysis.md`、`failure-tags.json`

