# Vision Package Contract V0.1

## Required Layout

每个正式 package 至少具备：

```text
<package>/
  SKILL.md
  evals/evals.json
  metadata/package.json
  metadata/source-map.json
```

## Optional Layout

```text
references/
scripts/
assets/
```

## Required Metadata

`metadata/package.json` 最少包含：

- `package_name`
- `skill_name`
- `category`
- `status`
- `version`
- `source_mode`
- `candidate_origin`

`metadata/source-map.json` 最少包含：

- `package_name`
- `source_mode`
- `demo_sources`
- `notes`

## Eval Entry Contract

`evals/evals.json` 最少包含：

- `skill_name`
- `evals[]`
  - `id`
  - `prompt`
  - `expected_output`
  - `files`
  - `expectations`

## Candidate Rule

主线 A 当前阶段的 candidate 来源只允许来自 demo：

- 直接迁移现有 demo `SKILL.md`
- 对现有 demo skill 做 package 化改造
- 对现有 demo 的结构、命名、metadata、评测进行补全

当前阶段不从 `vision-doc` / `skill-doc` 直接生成新的 candidate package。
