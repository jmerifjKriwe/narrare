# ADR-056 — Runtime-Evidence-Aware Adoption Commit Gate & True-Debt Baseline

> **Status:** ✅ Accepted + Implemented (2026-06-29)
>
> _Implementation note: the Retrofit-Plan (§1–6) landed atomically — pre-commit
> hook + `run_checks.py` now pass `--evidence-dir .evidence`, the `adoption_debt`
> baseline was regenerated to the single true-debt entry
> (`writing | inline_fallback_count | 1`), and a RULE-10 regression test guards the
> runtime-aware ratchet. Commits land after explicit user commit-approval (Freigabe);
> the immutable Decision sections below are unchanged._
> **Date:** 2026-06-29
> **Deciders:** Architecture Specialist (formalizing user-approved direction "X")
> **Amends:** ADR-045 (Decision 1 — enforcement-point letter) and redefines the
> `adoption_debt` baseline semantics
> **Related:** ADR-025, ADR-038, ADR-041, ADR-045, ADR-047, ADR-055,
> CONSTRAINTS.md RULE-11 / RULE-19 / RULE-22

---

## Context

ADR-045 made feature adoption a **runtime semantic contract**: `PASS` means
runtime-adopted, not merely "infrastructure exists." To that end it specifies
(Decision 1) that *"Default local **and CI** commands must either load the intended
evidence source or label the run `STATIC_ONLY`."* CI and `just check-adoption`
honour this. Two other local entry points do **not**:

| Entry point | Command | Loads runtime evidence? |
|---|---|---|
| CI (authoritative) `.github/workflows/ci.yml:127-131` | `run_all_probes.py --evidence-dir .evidence` → `check_adoption.py --evidence-dir .evidence` | ✅ regenerates probes → markers → check |
| `just check-adoption` (`justfile:393-395`) | `check_adoption.py --evidence-dir .evidence` | ✅ reads committed markers |
| `just check` → `scripts/run_checks.py:133` | `check_adoption.py` | ❌ marker-blind |
| pre-commit hook `adoption-score` (`.pre-commit-config.yaml:30-37`) | `uv run python scripts/check_adoption.py` | ❌ marker-blind |

The marker-blind paths satisfy the **spirit** of ADR-045 Decision 1 — they never
produce a *false* `PASS`, because the ratchet baseline (`ai-gate-baseline.json`)
already encodes every marker-blind runtime gap as governed debt, so the run exits
`GOVERNED_DEBT` (exit 0) rather than `PASS`. But they violate the **letter** of
Decision 1: they neither load the intended evidence source nor label the run
`STATIC_ONLY`.

This is not a latent bug — it is an **undocumented consequence** of how ADR-045
Slice 4 was implemented. Slice 4 named `just check-adoption` and CI for the
evidence-loading update; it did **not** name the pre-commit hook. The hook
inherited `run_checks.py`'s bare `check_adoption.py` invocation. The result is an
**SSOT wart** with one concrete, blocking symptom.

### The blocking symptom — the baseline cannot be cleaned

`scripts/architecture/ai-gate-baseline.json`'s `adoption_debt` array currently
encodes **≈121 mode fingerprints** as governed debt. The vast majority of these
are **already runtime-verified**: probes cover them and committed `.evidence/*.json`
markers prove it. The marker-blind baseline simply never learned this. Only **one
entry is true adoption debt**: `writing | inline_fallback_count | 1` (the governed
inline-fallback exception for test ergonomics, see `approved_exceptions`).

Because the baseline ratchet fails on *new* debt
(`check_adoption.py:262-270`, `compare_section`), the baseline is a one-directional
ratchet: it can shrink, but only if **every** gate that reads it agrees on what
"current debt" is. Today it cannot shrink:

- A runtime-aware run reports **≈1** fingerprint (`inline_fallback_count`).
- A marker-blind run (`just check`, pre-commit) reports **≈121** fingerprints
  (every runtime-required mode shows a gap, because no evidence was loaded).

If the baseline is trimmed to the true set (`{inline_fallback_count}`), the
marker-blind paths immediately see **≈120 "new" debt items** (current ⊄ baseline)
and **fail**. So the truthful cleanup is **blocked** by the marker-blind entry
points. The baseline is therefore forced to permanently encode marker-blind gaps
for modes that are, in reality, runtime-verified — an SSOT wart that masks the
true adoption-debt picture.

### Evidence artefact state

`.evidence/*.jsonl` is gitignored (`.gitignore:99`); `.evidence/*.json` markers
are **committed**. After checkout the markers are therefore always present and
safe to read. The commit-time hook reads committed markers; it does **not**
regenerate probes (CI remains the authoritative regenerator).

---

## Root Cause Analysis

### Symptom

The `adoption_debt` baseline cannot be made truthful. Removing the ≈120
runtime-resolved fingerprints fails `just check` / the commit hook.

### Why #1 — Why can't the baseline shrink?

Because two local gate entry points run `check_adoption.py` **marker-blind**
(without `--evidence-dir`), so they re-introduce the resolved fingerprints as
"current debt." The ratchet then sees them as growth and fails.

### Why #2 — Why do those entry points run marker-blind?

Because ADR-045 Slice 4 named `just check-adoption` and CI for the
evidence-loading update but not the pre-commit hook or `run_checks.py`. The hook
inherited `run_checks.py`'s bare invocation, and nothing closed the gap.

### Why #3 — Why did the ADR's letter not catch this?

ADR-045 Decision 1 states the principle ("load evidence or label `STATIC_ONLY`")
but Slice 4 enumerated the concrete entry points to update and omitted the hook.
The marker-blind tier was never a *decided* feature — it is an undocumented
consequence. Its spirit (no false PASS) is preserved, but its letter is violated,
and the wart leaks into the baseline as fake "debt."

### Architectural design response

Make every local gate entry point **runtime-evidence-aware**, so that commit-time,
`just check`, `just check-adoption`, and CI all agree on what "current adoption
debt" is. Then redefine the baseline to track **true** debt (runtime-evidence-aware),
which shrinks it to its single honest entry and unblocks the cleanup.

---

## Decision Drivers

- **ADR-045 Decision 1 (letter):** default local **and** CI commands must either
  load the intended evidence source or label the run `STATIC_ONLY`. The pre-commit
  hook and `run_checks.py` currently do neither.
- **SSOT / baseline truth:** a baseline that encodes marker-blind gaps for
  runtime-verified modes is an SSOT wart. `GOVERNED_DEBT` must mean *real* debt,
  not "debt visible only to a blind gate."
- **Commit ↔ CI consistency:** a developer's commit-time gate and CI should agree
  on adoption status. Today the commit hook is marker-blind while CI is
  runtime-aware; the only reason both pass is the inflated baseline.
- **ADR-047 governance-health aggregation:** the governance-health report consumes
  the adoption checker's status output. A baseline whose *meaning* is "marker-blind
  gaps" makes the aggregated `GOVERNED_DEBT` reading misleading. Shrinking it is a
  one-directional ratchet improvement (debt only decreases) but its **semantics**
  change (from "marker-blind gaps" → "true debt") — ADR-047 coherence must hold.
- **Commit speed:** negligible. `.evidence/*.json` markers are small committed
  files; a sub-millisecond read at commit time. The hook **reads** markers; it does
  **not** regenerate probes, so it stays fast.

---

## Options Considered

### Option A — Status quo (marker-blind pre-commit + `run_checks.py`, inflated baseline)

Leave the marker-blind tier in place and keep the baseline encoding ≈121
fingerprints.

**Pros:**
- Zero change; CI and the spirit of ADR-045 (no false PASS) remain intact.

**Cons:**
- **Rejects the cleanup.** The `character_voice` runtime verification
  (commit `ee1cfc50`) and the just-fixed `fact_extraction` / `temporal_consistency`
  probes remain permanently misrepresented as "debt."
- The baseline is an SSOT wart: it cannot be made truthful.
- Violates the *letter* of ADR-045 Decision 1.
- The ADR-047 governance-health `GOVERNED_DEBT` reading is misleading.

### Option B — Docs-only formalization of the marker-blind tier

Accept the marker-blind tier as an intentional "fast local gate" and document it
as such (e.g., a new `STATIC_ONLY`-equivalent tier), leaving the baseline inflated.

**Pros:**
- No mechanics change; cheap.

**Cons:**
- Leaves the SSOT wart and the inflated baseline in place — the wart is the
  problem, not its documentation.
- Blocks the baseline cleanup exactly as Option A.
- Introduces a third, weaker tier that ADR-045 never intended (Decision 1 wanted
  local gates to *load evidence*, not to be relabelled as a weaker kind of gate).
- Adds governance vocabulary without fixing the root cause.

### Option C — Runtime-evidence-aware commit gate + true-debt baseline (chosen)

Make the pre-commit `adoption-score` hook **and** `run_checks.py`'s adoption step
pass `--evidence-dir .evidence` (matching `just check-adoption` and CI), and
redefine the `adoption_debt` baseline to track true (runtime-evidence-aware) debt.

**Pros:**
- Satisfies ADR-045 Decision 1's letter for **all** local entry points.
- Commit-time, `just check`, `just check-adoption`, and CI all agree.
- Unblocks the baseline cleanup: it shrinks to the single honest entry
  (`writing | inline_fallback_count | 1`).
- Gate behaviour for **genuinely new** debt is **unchanged** — a new mode without
  probes/markers still fails at commit time (no committed marker → runtime gap →
  not in baseline → FAIL). This is *intended* and an improvement (commit catches
  it, not just CI).
- ADR-047 aggregation reads a truthful `GOVERNED_DEBT` (one-directional ratchet
  improvement; debt only decreases).
- Negligible commit-time cost (reads committed markers, does not regenerate probes).

**Cons:**
- Marker-freshness coupling: the commit gate now depends on committed `.evidence`
  markers being fresh. **Mitigation:** markers are committed (always present after
  checkout) and CI is the authoritative regenerator — a stale/corrupted marker is
  self-healing at the next CI run (probes regenerate → markers → check).
- Baseline-semantics change is *consumed* by ADR-047's aggregation; must verify the
  governance-health reading stays coherent (covered in Retrofit-Plan validation).

---

## Decision

**We choose Option C.**

1. **Pre-commit `adoption-score` hook** (`.pre-commit-config.yaml`) and
   **`run_checks.py`'s adoption step** (`scripts/run_checks.py:133`) SHALL pass
   `--evidence-dir .evidence`, making the local commit-time gate and `just check`
   runtime-evidence-aware — consistent with `just check-adoption` and CI. CI remains
   the **authoritative regenerator** (it runs `run_all_probes.py` → markers → check);
   the local hook only **reads** committed markers and does not regenerate probes.

2. **The `adoption_debt` baseline** (`scripts/architecture/ai-gate-baseline.json`)
   is **re-defined** to track **true** adoption debt (runtime-evidence-aware), not
   marker-blind gaps. The implementation regenerates the baseline from a
   runtime-aware `adoption_debt_fingerprints(report)` run, shrinking the
   `adoption_debt` array to its honest set — the single entry
   `writing | inline_fallback_count | 1`. Every other mode fingerprint resolves
   because all baseline-covered modes are now probe-covered (including
   `character_voice`, `fact_extraction`, `temporal_consistency`).

3. **ADR-045 Decision 1's letter is now satisfied** for all local entry points:
   each either loads the intended evidence source (pre-commit, `run_checks.py`,
   `just check-adoption`) or — for any future genuinely marker-blind path — emits
   `STATIC_ONLY`. There is no longer an unlabelled marker-blind default.

4. **Gate behaviour for genuinely new debt is unchanged.** A future mode without
   probe coverage has no committed marker, surfaces as a runtime gap at commit time,
   and fails identically to today's CI. This is intended: the commit gate should
   catch it, not defer it.

---

## Rationale

ADR-045 already decided the principle — local and CI gates must witness runtime
evidence. This ADR closes the implementation gap the original Slice 4 left open
(the pre-commit hook + `run_checks.py`), and it removes the consequence of that
gap (an inflated, untruthful baseline). The change is narrow and mechanical on the
gate side (two entry points gain `--evidence-dir .evidence`) but architecturally
meaningful on the semantics side: `GOVERNED_DEBT` comes to mean what its name says.

Option A preserves a wart whose only "benefit" is inertia. Option B documents the
wart instead of removing it — a textbook anti-pattern (architectural-discipline §4:
workarounds are forbidden; §7: "documented ≠ correct"). Option C is the simplest
**correct** solution: it makes the four gate entry points agree, makes the baseline
truthful, and keeps the ratchet's safety property (new debt fails) intact. It is
also low-risk because the runtime-aware path is already exercised daily by CI and
`just check-adoption`; this ADR extends that proven path to the two remaining
entry points.

The tradeoff consciously accepted is **marker-freshness coupling** at commit time.
This is acceptable because (a) markers are committed, so they exist after every
checkout, and (b) CI is the authoritative regenerator, so any marker drift is
self-correcting. The commit gate is a *fast local witness*, not a source of truth.

---

## Consequences

**Positive:**
- Commit-time, `just check`, `just check-adoption`, and CI agree on adoption status.
- The `adoption_debt` baseline shrinks to its single true entry; the ≈120
  runtime-resolved fingerprints stop masquerading as debt.
- ADR-045 Decision 1's letter is satisfied for every local entry point.
- The ADR-047 governance-health `GOVERNED_DEBT` reading becomes truthful.
- Genuinely new debt is caught **earlier** (at commit), not only at CI.
- ADR-045's implementation-status claim ("all 29 modes `runtime_verified`",
  previously inaccurate for `character_voice`) is now genuinely accurate (see
  "ADR-045 Implementation-Status Note" below).

**Negative / Tradeoffs:**
- Baseline-semantics change is consumed by ADR-047's aggregation. The
  governance-health report's `GOVERNED_DEBT` total drops; any consumer/test
  asserting the old inflated count must be updated (see Retrofit-Plan). This is a
  one-directional ratchet improvement (debt only decreases).
- Marker-freshness coupling: the commit gate depends on committed `.evidence`
  markers. Mitigated by committed markers + CI self-healing regeneration. If a
  developer commits with a corrupt/stale marker, CI catches it on push; the local
  gate remains a *witness*, not a *regenerator*.

**Constraints introduced / referenced:**
- ADR-045 Decision 1 enforcement-point letter (closed).
- RULE-11 (graceful degradation / no silent failure): runtime-aware local gates
  surface genuine gaps visibly rather than hiding them behind an inflated baseline.
- RULE-19 (baseline sync): the baseline must reflect reality across all gate
  entry points, not the blind spot of one of them.
- RULE-22 (cross-feature coherence): the baseline-semantics change must stay
  coherent with ADR-047's governance-health aggregation.

---

## ADR-045 Implementation-Status Note

ADR-045's implementation-status section (line ~670) claims *"all 29 modes are
`runtime_verified` and `adopted`."* This was previously **inaccurate** for
`character_voice`, which lacked probe coverage until commit `ee1cfc50`. It is now
accurate. The marker-blind commit gate obscured this inaccuracy: because the
baseline encoded `character_voice` gaps as "governed debt" and the marker-blind
gate never re-derived runtime facts, nothing surfaced the discrepancy at commit
time. **This ADR does not edit ADR-045** (it preserves the Accepted ADR's
immutable record); the Platform/Docs specialists may add a one-line cross-reference
to ADR-056 in ADR-045's implementation-status section when implementing, so the
historical claim is annotated with its correction. Editing ADR-045 in place is
**out of scope** for this ADR's own change.

---

## Retrofit-Plan

> This ADR changes gate **mechanics** (which entry points load evidence) and gate
> **semantics** (what the baseline means). Per the ADR process and architectural
> discipline, the change is fully specified here. Platform implements it after the
> user reviews this ADR. Each step is atomic and independently testable.

### 1. Inventory of affected paths

| Path | Symbol | Current | Change |
|---|---|---|---|
| `.pre-commit-config.yaml` | `adoption-score` hook (`:30-37`) | `entry: uv run python scripts/check_adoption.py` | add `args: ["--evidence-dir", ".evidence"]` (or append to `entry`) |
| `scripts/run_checks.py` | `Prompts` step adoption command (`:133`) | `(["uv","run","python","scripts","check_adoption.py"], None)` | append `"--evidence-dir", ".evidence"` to the argv list |
| `scripts/architecture/ai-gate-baseline.json` | `adoption_debt` array (`:5-127`) | ≈121 fingerprints (marker-blind gaps) | shrink to `["writing | inline_fallback_count | 1"]` (true debt) |

Unaffected (already runtime-aware): CI (`ci.yml:127-131`), `just check-adoption`
(`justfile:393-395`).

### 2. Migration steps (atomic, in order)

1. **Hook** — add `--evidence-dir .evidence` to the `adoption-score` pre-commit
   hook. Testable in isolation: run `uv run python scripts/check_adoption.py
   --evidence-dir .evidence` locally and confirm it exits 0 with
   `GOVERNED_DEBT` (before baseline shrink) / `PASS` semantics.
2. **`run_checks.py`** — add `--evidence-dir .evidence` to the adoption argv at
   `run_checks.py:133`. Testable: `just check` reports the same adoption status as
   `just check-adoption`.
3. **Baseline shrink** — regenerate `adoption_debt` from a runtime-aware
   `adoption_debt_fingerprints(report)` run (the baseline array is the serialized
   `stable_fingerprint()` set). Write the resulting single-entry array
   (`writing | inline_fallback_count | 1`) to `ai-gate-baseline.json`. The
   implementer derives the new set programmatically from a `--json` run rather than
   hand-editing, to avoid transcription error.

Steps 1–2 must land **together with** step 3 in the same change: shrinking the
baseline while a marker-blind entry point still exists would fail that entry point
(the root symptom). The order is presented for clarity; the change is atomic.

### 3. Breaking-change assessment

- **Genuinely new debt:** **no behaviour change.** A new mode without probe
  coverage / committed marker surfaces as a runtime gap and fails identically at
  commit (it now fails *earlier* — at commit, not only CI). This is intended.
- **Existing governed debt:** the ratchet only **tightens** (one-directional; debt
  decreases). No previously-passing legitimate path regresses.
- **`Deps`/`Protocol`/schema changes:** none. No contract or data model changes;
  this is a gate-wiring + baseline-content change only.
- **`--evidence-repo` / `--static-only` mutual exclusions:** unchanged
  (`check_adoption.py:195-203`). No CLI surface change.

### 4. Checker update plan

- No checker **logic** changes are required. `check_adoption.py` already supports
  `--evidence-dir`; this ADR only changes **which callers pass it**.
- The baseline content change is the ratchet update itself (step 3). No new
  baseline file or section is introduced.

### 5. Test update plan

- `tests/unit/scripts/test_check_adoption_runtime_semantics.py` uses synthetic
  registries and synthetic baselines; **no real-count assertion** changes. The
  flag-mutual-exclusion tests (`:248-281`) are unaffected. **Add** a regression
  test asserting the runtime-aware commit-gate behaviour: a marker set resolving a
  previously-debt mode no longer produces a runtime gap, and a deliberately
  un-probed mode still fails the baseline ratchet.
- `tests/unit/scripts/test_check_current_state_facts.py:57` asserts an **exception**
  count ("14 in ai-gate-baseline.json") — this is the `approved_exceptions` array,
  **not** `adoption_debt`, so it is unaffected. **Verify** this during
  implementation; do not assume.
- Grep for any test reading `DEFAULT_BASELINE_PATH` or asserting an
  `adoption_debt` length against the real file; update or remove any such coupling.
  (Investigation found none beyond the synthetic-baseline tests.)

### 6. Validation plan (Definition of Done)

- [ ] `just check-adoption` → green.
- [ ] `just check` → green (now runtime-aware).
- [ ] `just check-governance` → green; governance-health `GOVERNED_DEBT` reading
      reflects the shrunk baseline (verify ADR-047 coherence).
- [ ] `uv run python scripts/check_adoption.py --evidence-dir .evidence` reports
      the `adoption_debt` baseline reduced to the single `inline_fallback_count`
      entry.
- [ ] Deliberately un-probed mode still fails: temporarily remove a probe marker
      (or add a synthetic mode without probes) and confirm the commit gate fails
      with a "new adoption debt" ratchet violation; then revert.
- [ ] Pre-commit hook runs end-to-end on a sample commit and exits 0.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|---|---|---|
| RULE-11 | ✅ | Runtime-aware local gates surface genuine gaps visibly (FAIL) instead of hiding them behind an inflated baseline. No silent PASS. |
| RULE-19 | ✅ | Baseline now reflects reality across all gate entry points; the ratchet is consistent commit ↔ CI. |
| RULE-22 | ✅ | Baseline-semantics change stays coherent with ADR-047 governance-health aggregation (validated in Retrofit-Plan). |
| RULE-04 | ✅ | No file-size impact; a one-arg wiring change + a JSON content change. |
| RULE-06 | ✅ | No new responsibility added; `check_adoption.py` already owns `--evidence-dir`. |
| RULE-10 | ✅ | New regression test asserts the runtime-aware commit-gate behaviour and the new-debt-still-fails property. |
| (ADR-045 Decision 1) | ✅ | Enforcement-point letter now satisfied for all local entry points. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. As new modes gain probe coverage, their
   fingerprints naturally leave the (runtime-aware) debt set; as new debt appears,
   it fails at commit. The baseline tracks truth, not a blind spot.
2. **Hard-to-undo coupling?** No. The change is additive on proven paths
   (`--evidence-dir` is already used by CI and `just check-adoption`). Reverting is
   a one-arg removal.
3. **Simplest correct solution?** Yes. Two entry points gain one flag; the baseline
   shrinks to its honest set. No new abstraction, no new tier, no new checker.
4. **Design intent clear?** Yes. "Commit, `just check`, `just check-adoption`, and
   CI all agree; `GOVERNED_DEBT` means real debt."

---

## Review Triggers

- A future mode lacks probe coverage → it surfaces at commit time (intended; this
  is the gate doing its job, not a regression to revisit).
- The `.evidence/` marker discipline changes (e.g., markers stop being committed)
  → re-evaluate whether the commit gate can still witness runtime evidence.
- `check_adoption.py`'s evidence-loading contract changes → re-confirm all entry
  points remain consistent.
- If a need emerges to run the adoption gate *without* evidence deliberately
  (e.g., offline), use the existing `--static-only` label rather than reverting to
  an unlabelled marker-blind default.
