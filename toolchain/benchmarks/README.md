# Benchmarks

这里放 Level 3 和 Level 4 相关的聚合工具。

当前脚本：
- `iteration_scaffold.py`
  - 为某个 package 准备 `iteration-N/` 目录和 `with_skill / without_skill` run scaffold
- `run_benchmark.py`
  - 对 iteration 下已有输出执行 grading，并生成 `benchmark.json` 与 `benchmark.md`
- `aggregate_benchmark.py`
  - 聚合各 run 的 `grading.json` / `timing.json`，计算对照统计与 delta
- `stability.py`
  - 在 benchmark 之后继续生成稳定性报告
  - 输出 `stability.json`、`stability.md`、`variance-by-expectation.json`

当前约定：
- 每个 run 目录下的主响应文件默认放在 `outputs/final_response.md`
- grader 会在 run 目录写入 `grading.json` 和 `metrics.json`
- benchmark runner 会在 iteration 根目录写入 `benchmark.json` 和 `benchmark.md`
- stability runner 会在 iteration 根目录写入 `stability.json` 和 `stability.md`
