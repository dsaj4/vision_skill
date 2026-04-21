# Vision Skill Kimi Production Line V0.1

## Summary

This version unifies three upstream and midstream activities under the same Kimi-driven operating model:

- eval set generation
- skill rewrite generation
- skill evaluation

The controller for every round is `Codex`, not Kimi itself.

Kimi generates candidate artifacts.
Codex validates, applies, triggers the next evaluation round, and writes the cycle summary.

## Mainline

```text
Codex controller
  -> Kimi eval draft
  -> optional apply to package evals/evals.json
  -> Kimi skill rewrite draft
  -> Codex validation
  -> optional apply to package SKILL.md and demo mirror
  -> Kimi differential eval
  -> optional Kimi host validation
  -> cycle summary
```

## Control Rules

- Kimi is the generation engine.
- Codex is the round controller.
- Package state changes happen only through Codex-controlled apply steps.
- Skill rewrite is not auto-applied when validation fails.
- Demo-origin packages must mirror the applied package skill back to their demo `SKILL.md`.

## Current Entry Point

```powershell
python -m toolchain.run_kimi_production_cycle `
  --package-dir "E:\Project\vision-lab\vision-skill\packages\golden-circle" `
  --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\golden-circle-workspace" `
  --apply-generated-evals `
  --apply-skill `
  --run-eval
```

Optional host validation:

```powershell
python -m toolchain.run_kimi_production_cycle `
  --package-dir "E:\Project\vision-lab\vision-skill\packages\golden-circle" `
  --workspace-dir "E:\Project\vision-lab\vision-skill\package-workspaces\golden-circle-workspace" `
  --run-host-validation
```

## Artifacts

Cycle artifacts are stored in:

```text
package-workspaces/<package>-workspace/cycles/<cycle-name>/
```

Key outputs:

- `eval-generation/eval-draft.json`
- `skill-rewrite/SKILL.generated.md`
- `skill-rewrite/validation.json`
- `cycle-summary.json`
- `cycle-summary.md`

The Kimi differential eval output remains in the package workspace root under:

```text
<cycle-name>-eval/
```

## Scope

This version solves orchestration and provider unification.

It does not yet auto-promote generated eval drafts into `eval-factory/certified-evals/`.
That promotion still belongs to the calibration and certification layer.
