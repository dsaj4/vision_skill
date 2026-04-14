# Vision Skill Differential Eval And Eval Factory Design V0.1

**Project:** `E:\Project\vision-lab\vision-skill`  
**Track:** `Evaluation Credibility / Mainline A`  
**Version:** `V0.1`  
**Created:** `2026-04-13`  
**Status:** `Draft for implementation review`

---

## 1. Intent

This design defines the next lightweight upgrade of the Vision skill evaluation system.

It focuses on two linked changes:

1. replace the current Level 3 scoring center with `differential evaluation` powered by `pairwise LLM judging`
2. add a lightweight `eval-factory` that produces calibrated eval sets instead of relying on ad hoc prompts

The goal is not to redesign the whole repository. The goal is to fix the current mismatch between the system and the real evaluation target:

> many candidate skills are already fairly strong, task scenes are often non-standardized, and the important differences are subtle, distributional, and boundary-sensitive rather than coarse structural gaps

---

## 2. Problem Statement

The current mainline is good at answering:

- did the package run
- did it produce the expected broad structure
- did it pass shallow capability checks

The current mainline is weak at answering:

- when two answers are both decent, which one is actually more helpful
- whether the skill adds real value in ambiguous or non-standardized tasks
- whether the skill improves boundary handling rather than only output polish
- whether the observed gain is stable across prompt variants

The main bottleneck is not only the grader. It is the combined shape of:

- shallow rule-based scoring
- eval prompts that are not calibrated for subtle discrimination
- summary logic centered on `single-answer pass rate`

---

## 3. Core Decision

This design adopts two explicit decisions.

### 3.1 Mainline Scoring Decision

Level 3 scoring should move from:

`single-answer rule grading`

to:

`pairwise differential judgment`

The key judgment question becomes:

> For the same task, is `with_skill` better than `without_skill`, and if so, how strongly and on which dimensions?

### 3.2 Eval Set Decision

Eval generation should move from:

`manually assembled prompt lists`

to:

`source -> scenario card -> candidate eval -> calibration -> certified eval`

Only calibrated evals should enter the formal benchmark set.

---

## 4. Design Goals

### 4.1 Primary Goals

- make the evaluation system sensitive to subtle quality differences
- support non-standardized tasks with multiple acceptable high-quality answers
- compare answers by user value rather than shallow format compliance
- add a lightweight process for generating and certifying high-quality evals

### 4.2 Non-Goals

This design does not aim to:

- replace the entire repository layout
- remove validators, executor, or review modules
- build a heavy data platform or database-backed eval service
- fully automate final release decisions

---

## 5. Mainline Upgrade

### 5.1 What Stays The Same

The following modules remain conceptually valid:

- Level 1: structural validation
- Level 2: protocol validation
- iteration scaffold
- executor and run artifact persistence
- Level 4-6 post-benchmark flow

The current file-contract style should be preserved.

### 5.2 What Changes

The current Level 3 center should be split into two parts:

- `Level 3A: Gate Check`
- `Level 3B: Differential Eval`

`Level 3A` keeps a reduced version of the current grader and only answers:

- is the output non-empty
- does it violate obvious protocol or boundary hard constraints
- is the response too malformed to compare

`Level 3B` becomes the real scoring layer and uses pairwise LLM judging.

### 5.3 New Level 3 Flow

The new benchmark path should be:

```text
scaffold
  -> execute with_skill / without_skill
  -> gate check each run
  -> pair matching by eval_id + run_number
  -> pairwise LLM judge
  -> consensus aggregation
  -> differential benchmark
```

### 5.4 Comparison Unit

The default comparison unit should be:

```text
same eval
same run number
with_skill/run-N
vs
without_skill/run-N
```

This is intentionally simple and reuses the current workspace layout.

### 5.5 New Core Outputs

The current outputs should be extended with:

- `pairwise-judgment.json`
- `pairwise-judgment-reversed.json`
- `pairwise-consensus.json`
- `differential-benchmark.json`
- `differential-benchmark.md`

The existing `grading.json` can remain as a gate-check artifact, but it should no longer be treated as the main value score.

### 5.6 New Summary Metrics

The benchmark summary should prioritize:

- `win_rate`
- `tie_rate`
- `avg_margin`
- `judge_disagreement_rate`
- `cost_adjusted_value`

The old metrics:

- `pass_rate`
- `time_seconds`
- `tokens`

should remain, but move to supporting signals rather than the primary decision surface.

### 5.7 New Lightweight Modules

Add:

- `toolchain/judges/pairwise_judge.py`
- `toolchain/judges/consensus.py`
- `toolchain/benchmarks/run_differential_benchmark.py`

Optional later:

- `toolchain/benchmarks/aggregate_differential_benchmark.py`

### 5.8 Prompt Strategy For Pairwise Judge

The prompt does not need to be finalized in this document, but its intended shape is:

- blind comparison only
- strict JSON output
- no absolute scoring as primary mechanism
- evaluation by user value, not by verbosity or formatting
- explicit tolerance for answer diversity
- explicit permission to return `tie`

The judge should compare along a small fixed rubric:

- Thinking Support
- Tradeoff Quality
- Actionability
- Judgment Preservation
- Boundary Safety

The pair should be judged twice:

- `A/B`
- `B/A`

If the two judgments disagree, a third tiebreaking pass should be allowed.

This is enough for a first stable implementation and avoids a heavy multi-model voting design.

### 5.9 Migration Rule

The upgrade should be introduced in two phases.

#### Phase 1: Parallel Run

Keep:

- current `grading.json`
- current `benchmark.json`

Add:

- differential artifacts in parallel

Use this phase to compare:

- old rule-based summary
- new differential summary

#### Phase 2: Mainline Switch

After the new path stabilizes:

- make `differential-benchmark.json` the primary Level 3 artifact
- keep old grading only for gate checks and backward compatibility

---

## 6. Eval Factory Design

### 6.1 Purpose

The eval-factory exists to make eval quality a first-class engineering concern.

It should produce evals that are:

- realistic
- discriminative
- boundary-aware
- stable under judging

### 6.2 Lightweight Repository Layout

Create:

```text
eval-factory/
  source-bank/
  scenario-cards/
  eval-candidates/
  certified-evals/
  calibration-reports/
```

This should remain file-based and lightweight. No database is required in V0.1.

### 6.3 Flow

The eval-factory flow should be:

```text
source-bank
  -> scenario-card
  -> eval-candidate
  -> calibration
  -> certified-eval
```

### 6.4 Minimal Data Contracts

#### Source Bank

Stores raw materials such as:

- real user prompts
- historical failures
- strong ambiguity cases
- boundary-sensitive cases

Minimal fields:

- `source_id`
- `task_family`
- `raw_text`
- `source_type`
- `notes`

#### Scenario Card

Turns one raw case into a reusable task abstraction.

Minimal fields:

- `scenario_id`
- `task_family`
- `task_goal`
- `user_state`
- `constraints`
- `hidden_tradeoff`
- `boundary_axes`
- `acceptable_diversity_notes`

#### Eval Candidate

Turns a scenario card into one benchmarkable question variant.

Minimal fields:

- `eval_id`
- `scenario_id`
- `variant_type`
- `prompt`
- `judge_rubric`
- `must_preserve`
- `must_not_do`

#### Certified Eval

Stores only evals that passed calibration.

Minimal fields:

- `eval_id`
- `scenario_id`
- `certification_status`
- `discriminative_score`
- `judge_agreement_score`
- `notes`

### 6.5 Candidate Variant Policy

To stay lightweight, each scenario card should generate at most four candidate variants:

- `base`
- `paraphrase`
- `info-missing`
- `boundary-stress`

This is enough to test robustness without exploding eval volume.

### 6.6 Calibration

Calibration is the central quality gate for evals.

Each candidate eval should be tested with:

- `without_skill`
- one known weak skill
- one known stronger skill
- `3 runs per configuration`

Each comparison should use the pairwise LLM judge.

The candidate eval passes certification only if all of the following are acceptable:

- strong skill beats weak skill often enough
- judge disagreement stays below threshold
- the eval does not collapse into trivial ties
- at least one meaningful difference appears on the intended comparison dimensions

### 6.7 Suggested First Thresholds

Use simple initial thresholds:

- `strong vs weak win_rate >= 0.70`
- `judge_agreement_score >= 0.75`
- `tie_rate < 0.60`

These are deliberately practical, not overly strict.

### 6.8 Formal Eval Set Construction

The first certified eval set should stay small.

Recommended starting size:

- `8 to 12 certified evals`

Suggested composition:

- `5 to 6` normal value-separation evals
- `2 to 3` information-insufficiency evals
- `2 to 3` boundary-stress evals

This is enough for a real signal without making every run too expensive.

---

## 7. Interaction Between Eval Factory And Mainline

The relationship should be:

```text
eval-factory builds and certifies evals
mainline consumes certified evals
```

The simplest first-step integration is:

- certified evals remain stored in `eval-factory/certified-evals/`
- package-level `evals/evals.json` is generated from or synchronized with the certified eval set

This avoids immediate deep restructuring of package layouts.

---

## 8. Risks

### 8.1 Judge Drift

Pure LLM judging may become unstable if prompts are too open or too long.

Mitigation:

- fixed schema
- fixed rubric
- A/B plus B/A judging
- calibration before certification

### 8.2 Overfitting To The Judge

Packages may learn to win the judge rather than help the user.

Mitigation:

- keep human review
- keep small hidden eval subsets later
- review disagreement-heavy cases

### 8.3 Eval Inflation

Generating too many candidate prompts can create maintenance burden.

Mitigation:

- limit to four variants per scenario card
- certify only a small formal set

### 8.4 Mainline Complexity Creep

A full rewrite would slow the project down.

Mitigation:

- keep validators, scaffold, executor, stability, analyzer, review structure
- only replace the Level 3 center

---

## 9. Implementation Plan

### Phase 1

- add pairwise judge module
- add consensus module
- add differential benchmark runner
- keep old grader as gate checker
- manually prepare 3 to 5 eval-factory scenario cards
- certify 4 to 6 evals

### Phase 2

- generate package eval files from certified evals
- make differential benchmark the default Level 3 output
- adapt stability, analysis, and review to prefer differential outputs

### Phase 3

- expand certified eval count
- add holdout evals
- add richer boundary coverage

---

## 10. Success Criteria

This upgrade should be considered successful if:

1. the new differential benchmark can distinguish subtle differences that the current pass-rate-centric path compresses
2. the eval-factory can produce a small certified set with stable judge agreement
3. the repository can run old and new Level 3 paths in parallel during migration
4. reviewers find the new benchmark outputs more decision-useful than the old summary alone

---

## 11. Immediate Next Actions

1. implement `pairwise_judge.py`
2. implement `consensus.py`
3. implement `run_differential_benchmark.py`
4. create `eval-factory/` with sample files
5. certify the first small eval batch
6. run one package through old and new benchmark paths in parallel
7. compare whether the new path exposes more useful differences

---

## 12. Revision Log

- `2026-04-13 / V0.1`
  - defined the lightweight differential-eval upgrade
  - moved Level 3 center from rule scoring to pairwise LLM comparison
  - defined a lightweight eval-factory with calibration before certification
