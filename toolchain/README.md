# Toolchain

这里是 `vision-skill` 的工程工具链。当前主链已经覆盖：

- `validators/`
  - Level 1-2
  - 校验 package 结构和协议约束
- `executors/`
  - Level 3
  - 执行 `with_skill / without_skill` 真实 run
- `graders/`
  - Level 3
  - 对单个 run 生成 `grading.json`
- `benchmarks/`
  - Level 3-4
  - 聚合 `benchmark` 与 `stability` 产物
- `analyzers/`
  - Level 5
  - 读取已有 artifacts，生成 `analysis.json`
- `reviews/`
  - Level 6
  - 生成人审包、评分模板和放行建议

当前还没有完整落地的模块：

- `builders/`
- `packagers/`

## 推荐阅读顺序

1. `validators/`
2. `executors/`
3. `graders/`
4. `benchmarks/`
5. `analyzers/`
6. `reviews/`

## 常用命令

先跑 Level 3：

```bash
python -m toolchain.benchmarks.run_benchmark
```

再从 benchmark 进入 Level 4-6：

```bash
python -m toolchain.run_level456 --iteration-dir "E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1" --package-dir "E:\Project\vision-lab\vision-skill\packages\swot-analysis"
```

这条命令会依次生成：

- `stability.json`
- `stability.md`
- `variance-by-expectation.json`
- `analysis.json`
- `analysis.md`
- `failure-tags.json`
- `human-review-packet.md`
- `release-recommendation.json`

如果 iteration 下还没有 `human-review-score.json`，它会自动写入模板。
如果已经有人填写过人审结果，默认不会覆盖；只有显式传入 `--refresh-review-template` 才会重写。
