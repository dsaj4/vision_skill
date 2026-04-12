# Graders

这里放各层 eval 的打分器。

当前脚本：
- `capability_grader.py`
  - 面向 Level 3
  - 读取 `eval_metadata.json` 和 `outputs/final_response.md`
  - 支持两类 assertion：
    - 字符串 expectation 的启发式判断
    - 结构化 assertion，例如 `contains_all`、`contains_any`、`contains_none`
  - 输出：
    - `grading.json`
    - `metrics.json`

当前目标不是做“完美语义评分”，而是先把 benchmark 主链打通，让 package 能进入 `with_skill / without_skill -> grading -> benchmark` 的最小闭环。
