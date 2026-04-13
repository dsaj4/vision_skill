# Vision Skill Eval Effectiveness Suite Design V0.1

**Project:** `E:\Project\vision-lab\vision-skill`  
**Track:** `Evaluation Credibility / Mainline A`  
**Version:** `V0.1`  
**Created:** `2026-04-13`  
**Status:** `Design approved for spec review`

---

## 1. Intent

This design defines a strict test suite whose purpose is not to prove that the current toolchain can produce benchmark files, but to answer a sharper question:

> Can the current evaluation system reliably separate genuinely helpful skills from ordinary or weak skills?

The suite focuses on one task family, keeps the task domain fixed, and creates a controlled quality gradient across multiple skill packages. The evaluation system is considered effective only if it can recover that gradient with stable and explainable benchmark outcomes.

---

## 2. Core Decision

This suite uses the `single-task quality-gradient` method.

The chosen task family is `SWOT analysis`.

Reasons:

- the current repository already has a canonical `swot-analysis` package
- the current graders, validators, analyzers, and workspace layout already understand SWOT-shaped outputs
- keeping the task family fixed reduces noise and makes score differences easier to attribute to package quality rather than task-type changes
- the existing sample package already exposed an important real weakness: protocol alignment and value expectations are not yet sharply separated

This suite therefore tests the evaluation system under controlled conditions instead of expanding to a broader but noisier multi-domain benchmark.

---

## 3. Goal And Non-Goals

### 3.1 Primary Goal

Build a package set and benchmark flow that can distinguish:

- truly helpful SWOT skill packages
- average or generic SWOT skill packages
- weak or nearly empty SWOT skill packages

### 3.2 Secondary Goals

- verify that protocol-sensitive packages do not get rewarded only for looking structured
- verify that stronger packages show value over `without_skill`, not only compliance with package structure
- produce a reusable suite that can be rerun after grader or benchmark changes

### 3.3 Non-Goals

This suite does not try to:

- test multiple task families in the same round
- prove resistance against adversarial or gaming-oriented skill designs
- redesign the entire benchmark pipeline
- replace human review with a fully automatic final decision

Those are valid future directions, but not the purpose of this first effectiveness suite.

---

## 4. Test Philosophy

The suite should answer the credibility question by combining two comparisons:

### 4.1 Within-Package Comparison

For every package variant:

- run `with_skill`
- run `without_skill`
- measure the delta

This answers whether a package adds value over baseline.

### 4.2 Across-Package Comparison

After all package variants run on the same eval set:

- compare benchmark deltas across packages
- compare value-proxy expectation pass rates across packages
- compare analysis failure tags across packages

This answers whether the evaluation system can recover the intended quality ordering.

The suite is successful only when both comparisons make sense together.

---

## 5. Package Set Design

The suite introduces seven package variants under one fixed task family.

### 5.1 Package List

1. `swot-null`
2. `swot-format-only`
3. `swot-enumeration-only`
4. `swot-generic-strategy`
5. `swot-practical-core`
6. `swot-strong-analyst`
7. `swot-strong-guardrailed`

### 5.2 Quality Gradient Definition

| Package | Design Intent | Expected Value Level | Why It Should Score There |
|---|---|---:|---|
| `swot-null` | almost empty behavior contract | very low | triggers but gives almost no usable guidance |
| `swot-format-only` | emphasizes layout and headings | low | output looks tidy but lacks real prioritization or strategy logic |
| `swot-enumeration-only` | lists S/W/O/T factors | low-mid | identifies factors but does not reason across them |
| `swot-generic-strategy` | adds generic next-step advice | medium-low | moves beyond enumeration but remains templated and shallow |
| `swot-practical-core` | adds prioritization and cross-strategy guidance | medium | becomes genuinely useful for normal cases |
| `swot-strong-analyst` | adds evidence, tradeoff handling, and action prioritization | high | should beat baseline clearly on value-proxy expectations |
| `swot-strong-guardrailed` | adds full protocol and fragile-state handling on top of strong analysis | highest | should combine value and protocol fidelity most consistently |

### 5.3 Expected Relative Ordering

The intended benchmark ordering is:

`swot-strong-guardrailed >= swot-strong-analyst > swot-practical-core > swot-generic-strategy > swot-enumeration-only > swot-format-only > swot-null`

This ordering is a design hypothesis and becomes the central evaluation target of the suite.

---

## 6. Shared Eval Set

All seven packages use the same eval set.

The suite uses `8 evals`, split into two groups.

### 6.1 Value-Separation Group

These evals are designed to create measurable differences between weak and strong packages.

1. `career-switch-sufficient-context`
   A user is considering a shift into AI product operations with mixed strengths and clear constraints.

2. `student-project-low-budget`
   A user wants to launch a small interview-prep project with very limited budget and real competition.

3. `small-business-entry-under-competition`
   A small founder is considering a niche market entry under pressure from stronger incumbents.

4. `personal-decision-with-tradeoffs`
   A user must choose between two meaningful paths with explicit cost, timing, and support constraints.

5. `long-mixed-signal-input`
   A long prompt mixes useful evidence, uncertainty, strengths, and contradictory risks.

6. `resource-limited-growth-choice`
   A user has one strong edge, two serious weaknesses, one near-term opening, and one structural threat.

These evals should reward packages that can do more than enumerate factors.

They should preferentially reward:

- prioritization
- cross-strategy analysis
- tradeoff framing
- actionable sequencing

### 6.2 Protocol-Safety Group

These evals are designed to confirm that stronger packages do not lose protocol fidelity.

7. `insufficient-information-followup`
   The prompt contains too little information and should trigger missing-info follow-up instead of premature full analysis.

8. `direct-result-mode`
   The prompt explicitly asks for a direct result without staged confirmation.

These evals do not exist mainly to create quality spread. They exist to stop the strongest packages from becoming protocol regressions.

### 6.3 Run Count

Each eval runs:

- `with_skill`
- `without_skill`
- `3 runs per configuration`

Full strict-suite volume:

- `7 packages`
- `8 evals`
- `2 configurations`
- `3 runs`
- total `336 model runs`

This is intentionally heavy. A smoke-test path is defined later to avoid paying that cost before the suite is wired correctly.

---

## 7. Assertion Model

Current SWOT grading relies too heavily on shallow structural checks. That is not enough to prove evaluation effectiveness.

The suite therefore separates expectations into three layers.

### 7.1 Layer A: Structural Assertions

These confirm that the package produced a recognizable SWOT-shaped response.

Examples:

- all four SWOT quadrants appear
- the output includes a usable structure
- the response includes strategy guidance or action guidance

These assertions are necessary but not sufficient.

### 7.2 Layer B: Protocol Assertions

These confirm that the package obeys the intended interaction mode.

Examples:

- insufficient information leads to follow-up instead of full completion
- direct-result request suppresses staged checkpoint prompts
- staged variants show real pause behavior where appropriate

These assertions prevent a strong-looking package from passing while violating its own contract.

### 7.3 Layer C: Value-Proxy Assertions

These are the most important additions for effectiveness testing.

Examples:

- `contains_priority_signal`
  Detects whether the response identifies the most important factors instead of only listing factors.

- `contains_cross_strategy_signal`
  Detects whether the response actually forms `SO / WO / ST / WT` style reasoning or equivalent cross-quadrant strategy logic.

- `contains_tradeoff_signal`
  Detects whether the response names conflicts, tradeoffs, risks of choice, or opportunity cost.

- `contains_action_plan_signal`
  Detects whether the response turns analysis into sequenced, concrete next steps.

These are still proxy assertions, not perfect truth measures. But they are much closer to "helpfulness" than simple keyword checks.

---

## 8. Monotonicity As The Key Success Signal

The strict suite adds one meta-level judgment that is not present in the current sample workspace:

### 8.1 Monotonicity Check

After all packages run, the suite should verify whether actual ranking roughly matches intended package quality.

The check should answer:

- do top-tier packages consistently beat mid-tier packages
- do mid-tier packages consistently beat weak packages
- do the bottom-tier packages fail to create meaningful delta over baseline

### 8.2 Practical Pass Rule

The suite does not require perfect strict ordering on every neighboring pair, because model variance can swap close neighbors.

The suite should be considered successful if:

- the top 2 packages rank above the middle 3 packages on overall value delta
- the middle 3 packages rank above the bottom 2 packages on overall value delta
- `swot-null` is in the bottom tier
- at least one of `swot-strong-analyst` or `swot-strong-guardrailed` is the top-ranked package

This rule is stricter than a vague qualitative claim, but more realistic than demanding perfect total ordering across all 7 packages.

---

## 9. Repository Layout

The suite should not be mixed into the canonical candidate package directory used for current submission review.

### 9.1 New Package Root

Create:

```text
packages-eval-effectiveness/
  swot-null/
  swot-format-only/
  swot-enumeration-only/
  swot-generic-strategy/
  swot-practical-core/
  swot-strong-analyst/
  swot-strong-guardrailed/
```

Each package follows the current package contract:

```text
<package>/
  SKILL.md
  evals/evals.json
  metadata/package.json
  metadata/source-map.json
```

### 9.2 New Workspace Root

Create:

```text
package-workspaces-eval-effectiveness/
  swot-null-workspace/
  swot-format-only-workspace/
  swot-enumeration-only-workspace/
  swot-generic-strategy-workspace/
  swot-practical-core-workspace/
  swot-strong-analyst-workspace/
  swot-strong-guardrailed-workspace/
```

Each workspace continues using the existing `iteration-N/eval-*/with_skill/run-*` contract.

This isolation protects the main example package from test-suite-specific noise while keeping the file contract unchanged.

---

## 10. Required Toolchain Changes

This design intentionally avoids large toolchain rewrites.

Only three focused changes are required.

### 10.1 Extend `capability_grader.py`

Add support for value-proxy assertions that can separate package quality more sharply.

Planned assertion support:

- `contains_priority_signal`
- `contains_cross_strategy_signal`
- `contains_tradeoff_signal`
- `contains_action_plan_signal`

The existing shallow SWOT checks should remain available for compatibility.

### 10.2 Add Batch Suite Runner

Add a small benchmark runner:

`toolchain/benchmarks/run_effectiveness_suite.py`

Responsibilities:

- iterate over the seven package variants
- scaffold iteration workspaces
- execute all evals for `with_skill` and `without_skill`
- run benchmark generation
- optionally run Level 4-6 post-processing
- emit an aggregate suite summary

### 10.3 Add Ordering Checker

Add:

`toolchain/benchmarks/check_effectiveness_order.py`

Responsibilities:

- read each package workspace benchmark
- compare observed ranking with intended ranking
- report whether the suite demonstrates effective separation
- explain where ranking mismatches occur

This tool supplements the current benchmark pipeline rather than replacing it.

---

## 11. Execution Plan

The suite should be implemented and validated in two phases.

### 11.1 Smoke Test Phase

Use two packages first:

- `swot-format-only`
- `swot-strong-guardrailed`

Use this phase to confirm:

- package validation passes
- protocol validation behaves as expected
- new assertion types are wired correctly
- iteration scaffold and batch runner work

### 11.2 Full Strict Phase

After smoke test success:

- create all seven packages
- scaffold all seven workspaces
- run the full `336-run` suite
- generate aggregate ordering report
- inspect benchmark, stability, analysis, and release-style outputs

This prevents expensive full-suite execution before the grader contract is stable.

---

## 12. Success Criteria

The strict suite is considered successful only if all of the following are true.

### 12.1 Protocol Success

Packages that should fail protocol-sensitive evals are clearly identified by Level 2 validation or protocol-related assertions.

### 12.2 Value Separation Success

Top-tier packages show clearly better value-proxy pass rates than bottom-tier packages.

### 12.3 Ordering Success

Observed package ranking broadly matches the intended quality gradient.

### 12.4 Explanation Success

Mechanism analysis can describe why weak packages lose and why strong packages win in terms that are useful for repair.

Without all four conditions, the suite cannot claim that the evaluation system has real discriminative power.

---

## 13. Known Risks

### 13.1 Keyword Proxy Inflation

Some weaker packages may still score too well if the grader remains overly keyword-driven.

Mitigation:

- add value-proxy assertion types
- inspect false-positive scoring during smoke test

### 13.2 Model Variance

Close package tiers may swap positions in single runs.

Mitigation:

- use `3 runs per configuration`
- evaluate by tier and mean delta, not single-run anecdotes

### 13.3 Strong Baseline Compression

`without_skill` may already perform well on straightforward SWOT prompts, reducing visible delta.

Mitigation:

- rely on mixed evals with prioritization and tradeoff pressure
- inspect package ordering, not only absolute delta size

### 13.4 Protocol-Value Tension

A package that preserves staged interaction may look worse if evals assume full one-shot completion.

Mitigation:

- keep explicit protocol evals
- keep explicit direct-result evals
- ensure expectations match the intended interaction mode of each prompt

---

## 14. Out Of Scope

This design does not include:

- anti-gaming or adversarial packages
- cross-domain packages beyond SWOT
- platform-wide CLI redesign
- automated human-review replacement

Those may become a `Phase 2` evaluation-credibility track after this suite is stable.

---

## 15. Acceptance For Implementation Start

Implementation should begin only after:

1. this design document is reviewed
2. the package list and eval count remain unchanged
3. the minimum grader extensions are accepted
4. the smoke-test-first rollout is accepted

Once those four conditions are satisfied, implementation can proceed without reopening the design.

---

## 16. Immediate Next Actions

1. create the seven effectiveness-test package directories
2. create one shared eval template and fan it out to all packages
3. extend `capability_grader.py` with value-proxy assertions
4. add `run_effectiveness_suite.py`
5. add `check_effectiveness_order.py`
6. run smoke test on two packages
7. run the full strict suite
8. summarize whether the current evaluation system truly separates helpful from weak skills

---

## 17. Revision Log

- `2026-04-13 / V0.1`
  - created the first strict design for an evaluation-effectiveness suite
  - fixed the task family to SWOT to reduce variance
  - defined 7 package variants, 8 shared evals, 3-run configurations, and monotonicity-based success criteria
