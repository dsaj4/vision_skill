# Vision Skill 代码理解指南 V0.1

**适用对象：** 代码基础较弱、但需要参与 `vision-skill` 工程维护的开发者  
**当前范围：** 已经落地的 `validate -> prepare -> execute -> grade -> benchmark` 主链  
**建议搭配阅读：**
- [系统总览](E:\Project\vision-lab\vision-skill\docs\project-plans\2026-04-08-vision-skill-mainline-a-system-overview-v0.1.md)
- [深度评测框架](E:\Project\vision-lab\vision-skill\docs\package-specs\deep-eval-framework-v0.1.md)

## 1. 先用一句话理解这个工程

这个工程不是“写几个 prompt”，而是在做一条可以反复运行的流程：

```text
package
  -> 校验它长得对不对
  -> 准备一轮评测目录
  -> 真正执行 with_skill / without_skill
  -> 给输出打分
  -> 汇总成 benchmark
```

所以，代码本质上不是一坨散脚本，而是一条流水线上的不同工位。

## 2. 先理解 3 个核心目录

### `packages/`

这里放正式的 skill package。

示例：
- [swot-analysis](E:\Project\vision-lab\vision-skill\packages\swot-analysis)

一个 package 里最重要的是：
- [SKILL.md](E:\Project\vision-lab\vision-skill\packages\swot-analysis\SKILL.md)
- [evals.json](E:\Project\vision-lab\vision-skill\packages\swot-analysis\evals\evals.json)
- [package.json](E:\Project\vision-lab\vision-skill\packages\swot-analysis\metadata\package.json)
- [source-map.json](E:\Project\vision-lab\vision-skill\packages\swot-analysis\metadata\source-map.json)

你可以把它理解为“被评测的对象”。

### `package-workspaces/`

这里放每个 package 的运行历史和证据。

示例：
- [swot-analysis-workspace](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace)

里面最重要的是：
- [history.json](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\history.json)
- [iteration-1](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1)

你可以把它理解为“实验记录本”。

### `toolchain/`

这里放真正执行工程逻辑的 Python 脚本。

当前已经落地的模块：
- `validators/`
- `benchmarks/`
- `graders/`
- `executors/`
- `analyzers/`
- `reviews/`

你可以把它理解为“流水线工具箱”。

## 3. 推荐阅读顺序

如果你代码基础比较弱，不建议一上来就读所有脚本。建议按下面顺序：

1. 先看 package 长什么样
   - [swot-analysis](E:\Project\vision-lab\vision-skill\packages\swot-analysis)
2. 再看一轮评测结果长什么样
   - [iteration-1](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1)
3. 再看脚本
   - [package_validator.py](E:\Project\vision-lab\vision-skill\toolchain\validators\package_validator.py)
   - [protocol_validator.py](E:\Project\vision-lab\vision-skill\toolchain\validators\protocol_validator.py)
   - [iteration_scaffold.py](E:\Project\vision-lab\vision-skill\toolchain\benchmarks\iteration_scaffold.py)
   - [dashscope_executor.py](E:\Project\vision-lab\vision-skill\toolchain\executors\dashscope_executor.py)
   - [capability_grader.py](E:\Project\vision-lab\vision-skill\toolchain\graders\capability_grader.py)
   - [run_benchmark.py](E:\Project\vision-lab\vision-skill\toolchain\benchmarks\run_benchmark.py)
   - [aggregate_benchmark.py](E:\Project\vision-lab\vision-skill\toolchain\benchmarks\aggregate_benchmark.py)
   - [stability.py](E:\Project\vision-lab\vision-skill\toolchain\benchmarks\stability.py)
   - [mechanism_analyzer.py](E:\Project\vision-lab\vision-skill\toolchain\analyzers\mechanism_analyzer.py)
   - [cognitive_review.py](E:\Project\vision-lab\vision-skill\toolchain\reviews\cognitive_review.py)

这个顺序的原因很简单：先看“输入和输出”，再看“中间怎么做”。

## 4. 这条主链到底怎么跑

### 第一步：Level 1 结构校验

入口脚本：
- [package_validator.py](E:\Project\vision-lab\vision-skill\toolchain\validators\package_validator.py)

它的任务是检查 package 有没有最基本的骨架：
- `SKILL.md` 在不在
- `evals/evals.json` 在不在
- `metadata/package.json` 在不在
- `metadata/source-map.json` 在不在
- 这些 JSON 里关键字段有没有缺失
- `SKILL.md` frontmatter 是否合法

可以把它理解为“入场安检”。

你读这个文件时，重点看这几个函数：
- `_validate_skill_markdown`
- `_validate_package_json`
- `_validate_source_map_json`
- `_validate_evals_json`
- `validate_package`

其中真正的入口是 `validate_package`。前面的 `_xxx` 函数都是 helper，可以理解成“分工明确的小工具”。

### 第二步：Level 2 协议校验

入口脚本：
- [protocol_validator.py](E:\Project\vision-lab\vision-skill\toolchain\validators\protocol_validator.py)

这一步不是看“文件在不在”，而是看 skill 是否遵守我们定义的交互协议，比如：
- 有没有 `## 交互模式`
- 有没有 `Step 0`
- `Step 1-3` 是否都包含暂停块
- 暂停块里有没有 `继续 / 不对 / 直接要结果`
- 有没有 `## 规则`
- 有没有高压状态的 guardrail
- 有没有 `## 使用说明`

可以把它理解为“这个 skill 会不会按约定方式说话”。

你读这个文件时，重点看：
- `_extract_step_section`
- `validate_protocol`

这份代码的特点是：它没有调用模型，只是在静态检查文本内容。

### 第三步：准备一轮 iteration

入口脚本：
- [iteration_scaffold.py](E:\Project\vision-lab\vision-skill\toolchain\benchmarks\iteration_scaffold.py)

这一步做的事情很工程化，但很好理解：
- 读取 package 的 `evals.json`
- 在 workspace 下创建 `iteration-N`
- 为每个 eval 建目录
- 为每个 eval 建 `with_skill` 和 `without_skill`
- 为每个 run 预留 `outputs/`
- 写 `eval_metadata.json`
- 更新 `history.json`

你可以把它理解为“先把实验台搭好，再开始做实验”。

最重要的入口函数：
- `prepare_iteration`

这一层非常关键，因为它把 package 和 workspace 连接起来了。

### 第四步：真实执行 run

入口脚本：
- [dashscope_executor.py](E:\Project\vision-lab\vision-skill\toolchain\executors\dashscope_executor.py)

这是目前最像“真正跑起来了”的一层。

它会做这些事：
- 读取 `eval_metadata.json`
- 根据 run 是 `with_skill` 还是 `without_skill` 决定是否把 `SKILL.md` 注入给模型
- 组装请求消息
- 调用 DashScope 的 Chat Completions 接口
- 把返回结果写回 run 目录

这层会生成的真实产物包括：
- `request.json`
- `raw_response.json`
- `transcript.json`
- `timing.json`
- `outputs/final_response.md`

你读这个文件时，建议按这个顺序：

1. `build_messages`
   - 理解“with_skill”和“without_skill”的差别
2. `execute_run`
   - 理解单个 run 是怎么执行的
3. `execute_iteration`
   - 理解一整轮 iteration 是怎么循环执行的

辅助函数里最值得注意的是：
- `_resolve_model`
- `_resolve_endpoint`
- `_resolve_api_key`
- `_extract_assistant_text`

这些函数的作用是把“环境变量、HTTP 接口、响应解析”这些细节藏起来，避免主流程太乱。

### 第五步：给输出打分

入口脚本：
- [capability_grader.py](E:\Project\vision-lab\vision-skill\toolchain\graders\capability_grader.py)

这一步读的是模型已经生成好的输出文件，而不是重新跑模型。

它做的事情是：
- 找到 `outputs/final_response.md`
- 读取 `eval_metadata.json` 中的 assertions
- 把 assertions 标准化
- 检查输出有没有满足这些 expectation
- 生成 `grading.json` 和 `metrics.json`

你可以把它理解为“给每份答卷判分”。

这份代码里最重要的函数有 3 个：
- `_normalize_assertion`
- `_evaluate_assertion`
- `grade_run`

理解这三个函数之后，你就能看明白为什么某个 run 会被判定为通过或失败。

这里要特别注意一个现实问题：
- 当前 grader 不是“完美语义理解器”
- 它更像一个“第一版、规则驱动的自动评分器”

也就是说：
- 它很适合先把 benchmark 主链跑通
- 但不适合把它当成最终真理

### 第六步：汇总 benchmark

入口脚本：
- [run_benchmark.py](E:\Project\vision-lab\vision-skill\toolchain\benchmarks\run_benchmark.py)
- [aggregate_benchmark.py](E:\Project\vision-lab\vision-skill\toolchain\benchmarks\aggregate_benchmark.py)

这一步的分工是：

`run_benchmark.py`
- 遍历 iteration 下的所有 run
- 调用 `grade_run`
- 产出 iteration 级 `benchmark.json` 和 `benchmark.md`

`aggregate_benchmark.py`
- 读取每个 run 的 `grading.json`
- 计算通过率、耗时、token 的均值和波动
- 做 `with_skill` 和 `without_skill` 的对照

你可以把它理解为“把单次考试成绩汇总成班级成绩单”。

### 第七步：看稳定性

入口脚本：
- [stability.py](E:\Project\vision-lab\vision-skill\toolchain\benchmarks\stability.py)

这一层是在 benchmark 之后继续往下看：
- 同一个 eval 多次跑时，结果会不会漂
- 哪条 expectation 会随机掉线
- `with_skill` 是否比 baseline 更不稳定
- `with_skill` 是否没有更好，但成本反而更高

它会生成：
- `stability.json`
- `stability.md`
- `variance-by-expectation.json`

你可以把它理解为“不是看一次考得好不好，而是看这个人稳不稳”。

### 第八步：做机制分析

入口脚本：
- [mechanism_analyzer.py](E:\Project\vision-lab\vision-skill\toolchain\analyzers\mechanism_analyzer.py)

这一层不重新跑模型，而是读已有 artifacts，回答：
- 哪些 skill instruction 真的起作用了
- 为什么 with_skill 赢了或者没赢
- 问题更像是 `source`、`blueprint-spec`、`template` 还是 `skill-content`

它会生成：
- `analysis.json`
- `analysis.md`
- `failure-tags.json`

你可以把它理解为“考后复盘报告”。

### 第九步：做人审包

入口脚本：
- [cognitive_review.py](E:\Project\vision-lab\vision-skill\toolchain\reviews\cognitive_review.py)

这一层不自动拍板，而是自动整理材料给人看：
- 选出最值得看的代表性 run
- 预填 rubric 建议分
- 生成人工评分模板
- 生成 release recommendation

它会生成：
- `human-review-packet.md`
- `human-review-score.json`
- `release-recommendation.json`

你可以把它理解为“把所有证据打包给 reviewer，最后决定仍由人来做”。

## 5. 真实例子：`swot-analysis` 是怎么跑完一轮的

当前我们已经用下面这个 package 跑通了一轮真实 Level 3：
- [swot-analysis](E:\Project\vision-lab\vision-skill\packages\swot-analysis)

对应 workspace：
- [swot-analysis-workspace](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace)

当前可直接看的关键产物有：
- [history.json](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\history.json)
- [eval_metadata.json](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1\eval-1-ai-swot\eval_metadata.json)
- [with_skill final_response](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1\eval-1-ai-swot\with_skill\run-1\outputs\final_response.md)
- [without_skill final_response](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1\eval-1-ai-swot\without_skill\run-1\outputs\final_response.md)
- [with_skill grading](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1\eval-1-ai-swot\with_skill\run-1\grading.json)
- [benchmark.md](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1\benchmark.md)

如果你只想最快理解全链路，可以顺着这些文件看：

```text
packages/swot-analysis/evals/evals.json
  -> package-workspaces/swot-analysis-workspace/iteration-1/eval-1-ai-swot/eval_metadata.json
  -> with_skill/run-1/request.json
  -> with_skill/run-1/outputs/final_response.md
  -> with_skill/run-1/grading.json
  -> iteration-1/benchmark.md
```

## 6. 给弱代码背景开发者的阅读技巧

### 技巧 1：先找“入口函数”

不要一开始就逐行读。先找入口函数：
- `validate_package`
- `validate_protocol`
- `prepare_iteration`
- `execute_run`
- `execute_iteration`
- `grade_run`
- `grade_iteration_runs`

看到入口函数后，再往里看 helper。

### 技巧 2：先看“读了什么文件，写了什么文件”

对这个仓库来说，很多理解都可以靠文件流向完成，而不是靠算法。

例如：
- `prepare_iteration` 读 `evals.json`，写 `eval_metadata.json`
- `execute_run` 读 `eval_metadata.json`，写 `final_response.md`
- `grade_run` 读 `final_response.md`，写 `grading.json`
- `generate_benchmark` 读 `grading.json`，写 `benchmark.json`

只要你抓住这个读写关系，代码就不会显得抽象。

### 技巧 3：helper 函数不要怕

很多 `_load_json`、`_write_json`、`_resolve_model` 看起来函数很多，其实是在“把重复动作拆出去”。

这样做的好处是：
- 主流程更短
- 更容易测试
- 更容易换 provider 或换规则

所以看到很多小函数，不代表系统复杂；很多时候恰恰代表它被拆清楚了。

## 7. 当前主链的实际边界

这部分很重要，因为它能帮你避免误解现状。

当前已经完成的：
- Level 1 结构校验
- Level 2 协议校验
- iteration scaffold
- 真实 DashScope executor
- capability grader
- benchmark 聚合
- stability report
- mechanism analysis
- cognitive review packet
- `swot-analysis` 的真实 Level 3 跑通

当前还没有完成的：
- 通用 CLI 命令入口
- 更强的语义级 grader
- 自动写回 `history.json` 的阶段升级逻辑
- 完整的 Level 4 多轮真实核心包批量运行
- 更强的 Level 5 机制信号提取
- 更成熟的 Level 6 人审流程闭环

也就是说，我们现在已经不是“空规划”，但也还远没到“完整平台”。

## 8. 当前代码里最值得优先理解的设计思路

### 思路 1：用文件契约串联模块

模块之间不是直接强耦合调用，而是靠固定文件契约连接：
- `evals.json`
- `eval_metadata.json`
- `final_response.md`
- `grading.json`
- `benchmark.json`

好处是：
- 容易调试
- 容易插入人工检查
- 容易替换某一层实现

### 思路 2：先做最小闭环，再做更强智能

我们没有一开始就上复杂 orchestrator，而是先把这条最小闭环打通：

```text
prepare
  -> execute
  -> grade
  -> benchmark
```

这条链一旦通了，后面加强任意一层都会更稳。

### 思路 3：先让结果“可看见”

这个仓库很重视证据落盘。

例如真实 run 会留下：
- 请求
- 原始响应
- 最终输出
- timing
- transcript
- grading
- benchmark

这样做的意义是：
- 失败时可以追原因
- 规则有问题时可以回看
- 以后换 grader 或换模型时可以复用历史产物

## 9. 如果你要继续接手维护，建议先做什么

推荐的最低成本上手方式：

1. 先完整看一遍 [swot-analysis](E:\Project\vision-lab\vision-skill\packages\swot-analysis) 和它的 [iteration-1](E:\Project\vision-lab\vision-skill\package-workspaces\swot-analysis-workspace\iteration-1)
2. 再看 [test_package_validator.py](E:\Project\vision-lab\vision-skill\toolchain\validators\tests\test_package_validator.py) 和 [test_dashscope_executor.py](E:\Project\vision-lab\vision-skill\toolchain\executors\tests\test_dashscope_executor.py)
3. 最后再看生产代码

原因是：
- 测试文件通常比生产代码更直白
- 它们会告诉你“作者想让这个脚本做什么”

## 10. 后续维护建议

这份文档建议作为“活文档”维护。后面每次主链有新增模块时，建议同步补 3 件事：

1. 它在整条流水线中的位置是什么
2. 它读什么文件、写什么文件
3. 它的入口函数是什么

只要坚持这样维护，后面即使新同学代码基础弱，也能顺着这份文档把系统读明白。
