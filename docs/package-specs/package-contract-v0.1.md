# Vision Package Contract V0.1

## Required Layout

Every formal package should contain at least:

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

`metadata/package.json` should contain at least:

- `package_name`
- `skill_name`
- `category`
- `status`
- `version`
- `source_mode`
- `candidate_origin`

`metadata/source-map.json` should contain at least:

- `package_name`
- `source_mode`
- `demo_sources`
- `notes`

## Eval Entry Contract

`evals/evals.json` should contain at least:

- `skill_name`
- `evals[]`
  - `id`
  - `prompt`
  - `expected_output`
  - `files`
  - `expectations`

Optional per-eval fields:

- `host_eval`
  - `enabled`
  - `turn_script`
  - `expected_trigger`
  - `expected_trigger_signals`
  - `expected_protocol_path`

## Candidate Rule

Mainline A candidates are currently demo-origin only.

That means the allowed candidate path is:

- migrate an existing demo `SKILL.md`
- package an existing demo skill into the formal package structure
- backfill metadata, references, and evals around the demo asset

The current phase does not directly generate new candidate packages from `vision-doc` or `skill-doc`.

## Certified Eval Source

Packages may optionally declare a certified eval upstream in `metadata/package.json`:

```json
{
  "eval_source": {
    "mode": "certified-bundle",
    "bundle_path": "../../eval-factory/certified-evals/<package>/<bundle>.json",
    "sync_on_read": true,
    "sync_output": "evals/evals.json"
  }
}
```

When this field exists, the mainline resolves package evals through `toolchain.eval_factory.resolve_package_evals(...)` and can auto-refresh `evals/evals.json` before scaffold generation.

## Eval Source Resolution Rules

The current mainline resolves evals in this order:

1. If `metadata/package.json` declares `eval_source.mode = certified-bundle`, use the certified bundle as the upstream source.
2. If `sync_on_read = true`, refresh `evals/evals.json` before iteration scaffold creation.
3. Write stable sync metadata into `evals/eval-sync.json`.
4. If `eval_source` is absent, fall back to the package-local `evals/evals.json`.

Current expectations:

- `evals/evals.json` remains committed to the repository as a human-reviewable derived artifact.
- `eval-sync.json` should remain stable and should not record per-read timestamps.
- `prepare_iteration(...)` is the default entry point for consuming package evals and should not bypass eval resolution.
