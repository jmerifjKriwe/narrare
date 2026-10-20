# Throughput T10 — Write the review and report thresholds down once

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `f011ee28`
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Files authored:**
  - `docs/development/quality-gates.md` (new normative `## Review & report policy` section)
  - `AGENTS.md` (working-principle 5 replaced with a pointer)
  - `.opencode/agents/NarrareDevCoordinator.md` (numeric caps replaced with a pointer; two sites)
  - this report

## 1. Where the section landed, and why

`docs/development/quality-gates.md` has three existing sections after the intro:
`## Gate table`, `## Cadence & events`, `## Exception registry`. The new section sits
**after `## Cadence & events` and before `## Exception registry`** (lines 77–97).

Why there:

- The first three sections read as one arc: *which gates exist* (gate table) → *when
  they run* (cadence) → *how changes are sized, reviewed and reported* (new policy).
  The review/report thresholds are process gates on every change, so they belong with
  the normative gate material, not after it.
- `## Exception registry` is the closing appendix: it binds the gate table to CI
  reality (`scripts/gate-exceptions.json`, ADR-098) and its own presence rule. Putting
  the policy after it would separate the policy from the gate semantics it governs.
- The file has no explicit heading-order convention documented elsewhere, so the
  placement follows the existing narrative arc rather than a written rule.

The section body is the brief's block **verbatim** (machine-verified: extraction of
brief lines 21–41 vs. inserted lines 77–97, `diff` exit 0). That includes the marker
line `<!-- review-policy: caps=3/250 report=3/80 -->` at column 0, spelled exactly as
T11 expects.

## 2. Edits

### `docs/development/quality-gates.md`

One insertion of 22 lines, no other changes:

```diff
@@ -74,6 +74,28 @@ The authoritative trigger composition lives in `.github/workflows/ci.yml`
 - **Monthly** — mutation testing (`mutation-testing-monthly.yml`), non-blocking,
   issue report.

+## Review & report policy
+
+<!-- review-policy: caps=3/250 report=3/80 -->
+
+Normative text. `AGENTS.md` and `.opencode/agents/NarrareDevCoordinator.md`
+reference this section; they do not restate its numbers.
+
+- **Package caps:** ≤3 authored files and ≤250 new production LOC per delegated
+  unit. Test files, machine-generated artifacts and single-row documentation edits
+  do not count. Sub-slice rather than exceed.
+- **Per-task report file — required** when a task changes ≥3 authored files, adds
+  ≥80 new production LOC, crosses a layer boundary, or changes a governed surface
+  (`docs/_shared/CONSTRAINTS.md`, an ADR, `scripts/architecture/*`,
+  `.github/workflows/ci.yml`, `justfile`, `.pre-commit-config.yaml`). Otherwise the
+  commit message body is the record.
+- **Batch review — allowed** when the tasks share a layer and a file cluster and at
+  least one of them met the report threshold; the batch report names every covered
+  task.
+- **Per-task review — mandatory, never batched** when a task adds or renames a
+  Protocol/contract, changes a manifest or registry, changes the public shape of an
+  API response, or edits a governed surface.
+
 ## Exception registry
```

### `AGENTS.md`

Working principle 5 was the only place in the file that mentioned review, and the
file contained no package-cap numbers before the edit. Replaced one bullet with the
brief's pointer bullet:

```diff
-5. **Review non-trivial changes** (Reviewer subagent, edit: deny).
+5. **Review and report thresholds:** see `docs/development/quality-gates.md` §Review & report policy (normative; numbers are not restated here).
```

### `.opencode/agents/NarrareDevCoordinator.md`

Two numeric restatements existed, not one. Both now point at the normative section;
the heading and every behavioural rule are untouched.

```diff
@@ -300,7 +300,8 @@ window free: always delegate implementation.
 ## Package sizing (HARD)

 - One `task` delegation = exactly ONE logical unit with its own test cycle.
-  Cap: **≤ 3 files changed / ≤ 250 new LOC** per delegation.
+  Package caps: see `docs/development/quality-gates.md` §Review & report policy
+  (normative; numbers are not restated here).
 - Work beyond the cap MUST be sliced into a written plan BEFORE any
@@ -327,7 +328,7 @@ window free: always delegate implementation.
-5. **Execute**: delegate in layer order — **one plan-task per delegation (Package sizing cap: ≤3 files / ≤250 LOC)**. After each step: check the doc gate.
+5. **Execute**: delegate in layer order — **one plan-task per delegation (package caps per `docs/development/quality-gates.md` §Review & report policy)**. After each step: check the doc gate.
```

Behaviour preserved verbatim in both places: one delegation = one logical unit with
its own test cycle; plan-before-implementation for larger work; never dispatch a whole
feature in one `task` call; sub-slice a plan task that still exceeds the cap;
`PACKAGE_TOO_LARGE` → split and re-dispatch, never "do it anyway".

The second site (workflow step 5) was changed although the brief only named
`## Package sizing (HARD)`: the required sweep covers the whole file, and this was an
exact numeric restatement in a reference sentence — the category the task says must
be removed. Wording only; no rule semantics changed.

## 3. Verification (raw output)

### Doc drift

```text
$ uv run --all-packages python scripts/check_doc_drift.py --governance-only
── Governance Checks ──
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `analytics/writing_stats_recorder.py` which does not exist
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `chapters/service.py` which does not exist
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `coauthor_apply_service.py` which does not exist
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `importing/service.py` which does not exist
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `setup/demo_loader.py` which does not exist
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `analytics/writing_service.py` which does not exist
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `analytics/contracts.py` which does not exist
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `settings/writing_goals.py` which does not exist
  [WARNING] docs/features/analytics/STATS-001-writing-stats.md: References file `2026-10-07-stats001-writing-stats-design.md` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `analytics/router.py` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `analytics/service.py` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `analytics/contracts.py` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `llm/usage_events.py` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `llm/registry_run.py` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `llm/embedding_providers.py` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `analytics/usage_sink.py` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `_app/lifespan.py` which does not exist
  [WARNING] docs/features/analytics/STATS-002-cost-tracking.md: References file `analytics/middleware.py` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `PRODUCT.md` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `PRODUCT.md` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `PRODUCT.md` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `request.ts` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `lib/i18n/mergeOverlay.ts` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `lib/constants/tones.ts` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `packages/i18n/messages/{locale}/{ns}.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/de.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/fr.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/en.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `_scratch/ki_22.md` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `_scratch/ki_23.md` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/en.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/{locale}.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `request.ts` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `mergeOverlay.ts` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `request.ts` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/{locale}.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `mergeOverlay.ts` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/de.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/fr.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `overlays/formality/en.json` which does not exist
  [WARNING] docs/features/i18n/I-Copy-001-formality-register.md: References file `__tests__/i18n-request-formality.test.ts` which does not exist
  [WARNING] docs/features/kb/KB-009-kb-merge.md: References file `apps/api/narrare/kb/router_merge.py` which does not exist
  [WARNING] docs/features/planning/PLAN-001-scene-planning.md: References file `planning/router_scenes.py` which does not exist
  [WARNING] docs/features/planning/PLAN-001-scene-planning.md: References file `planning/scene_service.py` which does not exist
  [WARNING] docs/features/planning/PLAN-001-scene-planning.md: References file `planning/scene_ai_service.py` which does not exist
  [WARNING] docs/features/planning/PLAN-001-scene-planning.md: References file `planning/contracts.py` which does not exist
  [WARNING] docs/features/planning/PLAN-001-scene-planning.md: References file `core/agents/scene_plan_agent.py` which does not exist
  [WARNING] docs/features/planning/PLAN-001-scene-planning.md: References file `core/planning/scene_render.py` which does not exist
  [WARNING] docs/features/planning/PLAN-001-scene-planning.md: References file `2026-10-09-plan001-scene-planning-design.md` which does not exist
  [WARNING] docs/features/settings/SET-005-configurable-token-limits.md: References file `run_limits.py` which does not exist
  [WARNING] docs/features/setup/SETUP-003-import.md: References file `lib/api/core.ts` which does not exist
  [WARNING] docs/features/setup/SETUP-003-import.md: References file `next.config.ts` which does not exist
  [WARNING] docs/features/setup/SETUP-003-import.md: References file `lib/importing/simulateOperations.ts` which does not exist
  [WARNING] docs/features/setup/SETUP-003-import.md: References file `opsState.ts` which does not exist
  [WARNING] docs/features/setup/SETUP-003-import.md: References file `__fixtures__/operations-golden.json` which does not exist
  [WARNING] docs/features/setup/SETUP-003-import.md: References file `test_operations.py` which does not exist
  [WARNING] docs/features/setup/SETUP-003-import.md: References file `simulateOperations.test.ts` which does not exist

⚠️  57 doc drift warnings

✅ Doc drift check passed (with warnings)
EXIT=0
```

The 57 warnings are pre-existing feature-doc path citations (relative reference
resolution) and are unrelated to the three authored files; no warning names
`quality-gates.md`, `AGENTS.md` or the coordinator file. Exit 0 as required.

### Marker count

```text
$ grep -c 'review-policy' docs/development/quality-gates.md
1
```

Exactly one, the marker line (the heading uses `Review & report policy`, not the
token).

### Numeric-restatement sweep (required command)

```text
$ grep -rn '≤3 files\|≤ 3 files\|≤250\|≤ 250\|250 new' AGENTS.md .opencode/agents/NarrareDevCoordinator.md
EXIT=1
```

No output, exit 1 = no match. A broader pattern was also run to catch other spellings:

```text
$ grep -rn '≤3\|≤ 3\|≤250\|≤ 250\|250 LOC\|3 files' AGENTS.md .opencode/agents/NarrareDevCoordinator.md
BROAD_SWEEP_EXIT=1
```

### Verbatim check of the normative block

```text
$ sed -n '21,41p' .superpowers/sdd/.../task-10-brief.md > /tmp/opencode/t10-brief-section.md
$ sed -n '77,97p' docs/development/quality-gates.md > /tmp/opencode/t10-inserted.md
$ diff -u /tmp/opencode/t10-brief-section.md /tmp/opencode/t10-inserted.md
VERBATIM_DIFF_EXIT=0
```

### Gate drift (extra, read-only)

The quality-gates header says the file is machine-checked by `check_gate_drift.py`;
the new section is policy rather than a gate row, so this was confirmed unchanged:

```text
$ uv run --all-packages python scripts/check_gate_drift.py
GATE DRIFT REPORT
======================================================================
✅ ssot-present: Quality gates SSOT present at docs/development/quality-gates.md
✅ coverage-threshold: CI --cov-fail-under=80, documented target 80%
✅ streaming-compliance: Blocking in CI
✅ locale-sync: Blocking in CI

Summary: 0 critical, 0 warnings (all drifts have registered exceptions)
GATE_DRIFT_EXIT=0
```

## 4. Other restatements found (not fixed — outside the three authored files)

Live agent surfaces still restate the numeric caps. These are the next candidates for
pointing at the normative section; left untouched because the task constrains authored
files to the three above:

- `.opencode/agents/NarrareCoreSpecialist.md:221` — `Package cap: ≤3 files / ≤250 new LOC`
- `.opencode/agents/NarrareFrontendSpecialist.md:231` — same sentence
- `.opencode/agents/NarrareBackendSpecialist.md:224` — same sentence

Historical/spec surfaces (numbers are decisions of their own documents, not pointers):

- `docs/superpowers/specs/2026-10-19-dev-throughput-program-design.md:312` and `:353`
  — the spec's own P4 problem/decision statement.
- `docs/architecture/decisions/ADR-093-usage-event-sink-cost-persistence.md:221` — the
  ADR records the cap as a constraint it obeyed; immutable decision record.
- Numerous plan files under `docs/superpowers/plans/` and
  `docs/development/plans/` restate the caps in their Global Constraints. Those are
  point-in-time records of how each plan was sliced; rewriting them would rewrite
  history rather than remove a live restatement.

## 5. Concerns

1. **Spec vs. brief on the report threshold.** The spec's §6 decision text says a
   report is required at "≥2 production files" (line 330), while the brief's normative
   block and marker say `report=3/80` (≥3 authored files, ≥80 new production LOC).
   This task moved the brief's text verbatim and did not renegotiate numbers, so the
   normative document now says 3 while the spec prose says 2. This should be resolved
   deliberately (spec correction or an explicit note) before T11's checker is written
   against both.
2. **Three specialist agent files still restate the caps.** They are live instruction
   surfaces, so "referenced, not restated" is not yet fully true across `.opencode/`.
   T11's consistency checker will either flag them or must whitelist them; a small
   follow-up task should convert them to pointers.
3. **Coordinator workflow step 5 was edited beyond the named section.** Required by
   the whole-file sweep; wording only, rules intact. Flagged here because the brief
   said to change nothing else in that file.
4. **`AGENTS.md` no longer names the Reviewer subagent in principle 5.** The pointer
   bullet replaces "Review non-trivial changes (Reviewer subagent, edit: deny)". The
   subagent table further down still names `NarrareReviewerSpecialist` with
   `edit: deny`, and the normative section defines when review is mandatory, so the
   information is not lost — but the review trigger now lives in the gate document
   rather than in `AGENTS.md`.

## Coordinator ruling CR-3 (recorded after the implementer report)

The spec (`docs/superpowers/specs/2026-10-19-dev-throughput-program-design.md` §6)
requires a report when a task changes **≥2 production files** or adds ≥80 new
production LOC. The plan's T10/T11 text carried `report=3/80`, which would have
pinned a rule looser than the design — and T11 would have locked it into a checker.

Ruling: the spec is authoritative on this point; the plan text was the drafting
slip. The normative section now reads `report=2/80` and "≥2 production files", and
the plan file was corrected at every occurrence (global constraint, marker,
normative sentence, T11 interfaces, T11 test expectation) instead of leaving the
plan and the normative document disagreeing for T11 to inherit.

Also adjusted during review of this task: the `AGENTS.md` bullet keeps the review
obligation — "Review non-trivial changes and apply the report thresholds" — instead
of replacing it with a thresholds-only pointer. A pointer must not delete the duty
it points into.
