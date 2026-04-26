# Agent Skill Development Guide

Last updated: 2026-04-25

This guide is for agents working inside `vision-skill`. It explains how to use the project to create, improve, evaluate, and package skills without turning the repository back into a pile of hand-edited demos.

## Copy-Paste Agent Prompt

Use this prompt when assigning a skill development task to another coding agent:

```text
你是一个在 `vision-skill` 仓库内工作的 skill 开发 agent。

仓库根目录：
E:\Project\vision-lab\vision-skill

开始编辑前，先阅读这些文档：
1. README.md
2. docs/PROJECT.md
3. docs/AGENT_SKILL_DEVELOPMENT_GUIDE.md
4. toolchain/README.md
5. packages/README.md

你的任务是通过本项目的工程流水线开发或优化一个 skill package，而不是自由手写一段提示词后就结束。

默认工作流程：
1. 确认目标 package，位置应在 `packages/` 下。
2. 阅读该 package 的 `SKILL.md`、`metadata/package.json`、`metadata/source-map.json` 和 `evals/evals.json`。
3. 如果任务是优化已有 skill，先检查对应 `package-workspaces/*-workspace/iteration-*` 下最新可用的评测产物，尤其是：
   - `level3-summary.json`
   - `differential-benchmark.json`
   - `analysis.json`
   - `stability.json`
   - 如果有 host 评测，也检查 host 相关产物
4. 如果任务带有评测或优化性质，修改 skill 前先写或更新 optimization brief。
5. 每轮只做一个小而高影响的修改，用来验证一个清晰假设。
6. 保持 `SKILL.md` 是轻量核心行为契约，重点包含：
   - 触发行为
   - Step 0 路由
   - direct-result / missing-info / staged 三类分支
   - 输出契约
   - checkpoint 规则
   - 反模式
7. 较长的背景、示例、方法说明放进 `references/`，不要膨胀 `SKILL.md`。
8. 根据改动范围运行合适的 validator 和 eval。
9. 总结时说明改了什么、哪些证据变好或变差、下一轮应该验证什么。

重要约束：
- 不要把 demo 文本当成最终真相。demo 只是来源材料、迁移样本或风险样本。
- 除非明确要求，不要改 eval schema。
- 不要提交生成的模型 transcript、本地 workspace、cache、`.env` 或 API key。
- 不要只优化格式通过率。差分价值才是 Level 3 主信号。
- 不要把 staged interaction 做成默认仪式。信息充分时，应优先直接给出高质量结果。
- 没有评测证据和人工 review，不要声称 skill 已达到发布质量。
- 如果使用 Kimi Code，采用 workspace-file 模式：读取任务文件，写入指定 outputs，终端回复保持简短。
- 所有面向用户或总控 Codex 的汇报必须使用中文。

汇报时请用中文，并包含：
- 修改了哪些文件
- 运行了哪些验证命令
- 生成或检查了哪些评测产物
- 如果有指标，说明主要指标如何变化
- 当前剩余风险
- 下一轮建议验证什么
```

## Mental Model

The project treats a skill as an engineering asset:

```text
source/demo
  -> package
  -> certified or package evals
  -> Kimi Code differential evaluation
  -> stability and mechanism analysis
  -> host-agent validation
  -> human review
  -> release-ready artifact
```

The agent should therefore optimize the full loop, not just the wording of `SKILL.md`.

## First Files To Read

For any task, read only what is needed:

- `README.md`: repository-level overview and default commands.
- `docs/PROJECT.md`: current project shape and release rules.
- `toolchain/README.md`: command entrypoints and module boundaries.
- `packages/README.md`: package layout and package contract.
- `packages/<package>/SKILL.md`: current skill behavior.
- `packages/<package>/metadata/package.json`: package identity and eval source.
- `packages/<package>/evals/evals.json`: current eval cases.

When the task is optimization, also inspect latest artifacts:

- `package-workspaces/<package>-workspace/iteration-*/level3-summary.json`
- `package-workspaces/<package>-workspace/iteration-*/differential-benchmark.json`
- `package-workspaces/<package>-workspace/iteration-*/analysis.json`
- `package-workspaces/<package>-workspace/iteration-*/stability.json`
- `package-workspaces/<package>-workspace/iteration-*/host-benchmark.json` if host eval has run

## Development Workflow

### 1. New Skill From Demo

Use this when the user asks to turn a demo into a package.

Steps:

1. Identify the demo source and the intended package name.
2. Create or update `packages/<package>/`.
3. Add or update:
   - `SKILL.md`
   - `metadata/package.json`
   - `metadata/source-map.json`
   - `evals/evals.json`
   - optional `references/`
4. Keep the initial `SKILL.md` short and behavioral.
5. Add a small eval set that covers information-rich, information-missing, direct-result, continue, revise, and boundary cases.
6. Run package validation before running expensive evals.

### 2. Existing Skill Optimization

Use this when the user asks to improve a skill based on evaluation results.

Steps:

1. Inspect the latest Level 3-6 artifacts.
2. Identify one main failure mode.
3. Write a brief hypothesis, for example:
   - "If rich-input cases go direct-result by default, pairwise margin should improve."
   - "If checkpoint text is removed except where it has editing value, staged friction should drop."
4. Edit only the parts needed to test that hypothesis.
5. Run validator and the same eval set where possible.
6. Compare against previous results rather than relying on impression.

Preferred edit targets:

- Step 0 routing
- direct-result branch
- missing-info branch
- staged branch
- checkpoint rule
- output skeleton
- one or two high-quality examples
- anti-pattern list

Avoid mixing these in one iteration:

- trigger description rewrite
- protocol rewrite
- eval expansion
- host-lane expansion
- reference material rewrite

### 3. Kimi Code Worker Mode

Codex remains the controller. Kimi Code can be used as a worker.

Use the workspace-file pattern:

```text
Codex writes task bundle
  -> Kimi reads workspace files
  -> Kimi writes outputs/
  -> Codex validates outputs
  -> Codex applies accepted changes
  -> Codex runs evals
```

Do not require Kimi to return a full `SKILL.md` or large JSON in terminal text. Give it files to read and required output files to write.

Useful command:

```bash
python -m toolchain.run_kimi_production_cycle --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --apply-generated-evals --apply-skill --run-eval
```

## Validation And Evaluation

Run package validation first when a package changes:

```bash
python -m pytest toolchain/validators/tests
```

Run the default Kimi Code evaluation pipeline:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --runs-per-configuration 3
```

Run a fast smoke pass when debugging:

```bash
python -m toolchain.run_eval_pipeline --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --smoke
```

Run Kimi host validation when mainline evidence is promising:

```bash
python -m toolchain.agent_hosts.run_host_eval --host-backend kimi-code --package-dir "E:\Project\vision-lab\vision-skill\packages\<package>" --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\<package>-workspace" --iteration-number <N> --max-evals 4
```

## Quality Rules

Use these rules when editing skill content:

- `SKILL.md` is a behavior contract, not a textbook.
- The description should be clear and triggerable, but not bloated.
- Step 0 should classify the user state and ask only for missing information.
- If the user gives enough information, produce a direct result.
- If the user asks to co-create or the task is genuinely underspecified, use staged interaction.
- Checkpoints must help the user edit, continue, or redirect. Do not add fake checkpoints.
- Examples should show ideal behavior, not restate theory.
- Output should help the user think better, not just fill a framework.
- Failures must be assigned to a repair layer: `source`, `blueprint-spec`, `template`, or `skill-content`.

## What Counts As Progress

Good progress is evidence-backed:

- package validator remains valid
- `level3-summary.json` exists for the iteration
- `differential-benchmark.json` improves or clarifies failure
- `analysis.json` no longer shows the same primary failure
- stability flags are understood
- Kimi host validation confirms trigger and protocol behavior when required

Bad progress:

- prettier `SKILL.md` with no eval evidence
- higher format pass rate but worse pairwise result
- longer prompts that increase cost without better output
- staged protocol that feels like a ceremony
- claims of release quality without review

## Agent Report Template

Use this when finishing a task:

```text
Changed:
- <short list of files or package areas>

Validated:
- <commands run>

Evidence:
- <artifacts inspected or produced>
- <metric movement if available>

Decision:
- <continue / revise / hold / ready for human review>

Risks:
- <remaining uncertainty>

Next:
- <one recommended next iteration>
```
