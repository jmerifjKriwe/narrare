# ADR-062 — Governance Drift Automation Phase 2: Status SSOT Consistency & Review→Registry Linking (P3 + P5)

> **Status:** 🔄 Proposed
> **Date:** 2026-07-01
> **Deciders:** Architecture Specialist (recommendation; awaits Coordinator + User approval)
> **Supersedes:** —
> **Related:** ADR-047 (Governance Drift Automation — extends Phase 2/3 scope), ADR-041 (typed manifests / doc-drift), ADR-051 (RULE-18b matrix), ADR-060 / ADR-061, AUFG-01-01 / AUFG-01-02, CONSTRAINTS.md §8 (SSOT hierarchy)

---

## Context

ADR-047 established the central AUFG registry, the review-finding coverage checker, and
the SSOT/gate aggregation (`scripts/check_governance_health.py`). Review-01 (2026-07-01)
found two residual governance-drift classes that ADR-047's current checkers do not catch:

### P3 — Doc↔Doc status drift (no status SSOT)

A feature's adoption/health status is stated in **multiple documents** that can
contradict each other with no machine check. Concrete instance: `character_voice`
runtime adoption is described as `runtime-verified` in `CURRENT_STATE.md`, the
`ANAL-008` spec, and `check-adoption` output (ADR-057 ✅ Implemented, probes landed),
but `docs/features/INDEX.md:126` still states "`character_voice` runtime adoption =
governed debt". There is no checker that fails when free-text status prose in
`CURRENT_STATE.md` / `INDEX.md` / a feature spec contradicts the registry's lifecycle
state. ADR-047 Phase 3 aggregates *existing* drift checker outputs; it does not define a
single status SSOT or cross-check status prose against it.

### P5 — Review→registry linking is not enforced

Review files (`_audit/results/**/review-*.md`) introduce `### [AUFG-XX-YY]` task ids, but
nothing guarantees that every such id maps to a **consistent** registry entry: same id,
`source` pointing back to this review file, correct dependency paths, and no id collision
with an unrelated entry. Review-01 found exactly this: the registry's `AUFG-01-01` entry
cited `source: review-05-release.md` and dependency path `_retry.py` (both wrong — the
finding originates in `review-01-architektur.md` and the file is `retry.py`); the
registry's `AUFG-01-03` (MCP/A2A) collides with an editor/writing-hotspots task from
review-01 that was given the same id; and `AUFG-01-02` (character_voice) was missing
entirely. ADR-047's review-finding coverage checker verifies a finding *has* a lifecycle
entry; it does not verify the entry's *metadata is consistent* with the review that
originated it.

---

## Decision Drivers

- **SSOT discipline (CONSTRAINTS.md §8):** status claims must derive from one
  authoritative source; derived docs must not silently drift.
- **Architectural discipline §7:** a green governance check must cover the layer it
  implies — "registry exists" ≠ "registry metadata is correct".
- **RULE-22:** cross-artifact coherence (reviews ↔ registry ↔ status docs) must be
  checkable, not manually inspected.
- **RULE-04/06/07:** new checkers stay modular and read files/structured data only.
- **ADR-047 compatibility:** extend, do not duplicate, the governance-health layer.

---

## Options Considered

### Option A — Status quo (manual Architecture review)

The Architecture Specialist continues manually reconciling status prose across docs.

**Pros:** No tooling.

**Cons:** Preserves both drift classes (P3, P5) — proven to fail under load. Rejected.

### Option B — Single status SSOT + two consistency checkers (P3 + P5)

Designate the AUFG registry (`docs/architecture/governance/aufg-registry.md`) and the
Configuration Adoption Matrix as the **status SSOTs** for their respective domains, and
add two modular checkers: (P3) a doc↔status-SSOT consistency checker, and (P5) a
review→registry metadata-consistency checker.

**Pros:** Directly closes both drift classes; reuses the ADR-047 governance-health
aggregation surface; each checker is single-purpose.

**Cons:** Free-text status reconciliation (P3) is heuristic and needs a status-vocabulary
mapping + allowlist; P5 requires parsing `### [AUFG-XX-YY]` headers and cross-checking
registry fields.

### Option C — Generate all status docs from the registry (single direction)

Make `INDEX.md` / `CURRENT_STATE.md` status fragments *generated* from the registry,
eliminating drift by construction.

**Pros:** Strongest drift prevention (no hand-written status to drift).

**Cons:** Large change to long-form docs that mix status with narrative; generation
tooling is brittle for prose; out of proportion to the immediate need. Rejected for now
(may be revisited as a follow-up).

---

## Decision

**We choose Option B.** Two first-class measures, extending ADR-047's Phase 2/3 scope:

### P3 — Status SSOT consistency checker

- **Status SSOT:** the AUFG registry is the authoritative lifecycle state for AUFGs,
  accepted risks, and accepted enhancements; the Configuration Adoption Matrix is
  authoritative for configuration-effect lifecycle (per ADR-051). `CURRENT_STATE.md`,
  `docs/features/INDEX.md`, and feature specs are *derived* status surfaces.
- A checker fails when a status claim in a derived surface **contradicts** the registry/
  matrix state for the same subject (e.g. a feature marked `runtime-verified`/`stable` in
  the registry while a derived doc says `governed debt`, or vice versa).
- Mechanism: a small **status vocabulary** (`stable`, `adopted`, `runtime_verified`,
  `governed_debt`, `accepted_risk`, `planned`, `deprecated`, …) with an explicit
  contradiction table (e.g. `adopted` contradicts `governed_debt`), plus a governed
  allowlist for legitimately nuanced per-doc phrasing. The checker scans status-bearing
  lines/sections in derived docs and reconciles them against the SSOT.
- This concretely closes the `INDEX.md:126` ↔ registry contradiction for `character_voice`
  (AUFG-01-02): once AUFG-01-02's residual is fixed (Stage-3b updates `INDEX.md:126`),
  the checker prevents recurrence.

### P5 — Review→registry mandatory metadata linking

- Every `### [AUFG-XX-YY]` (and `### [CR-AUFG-XX-YY]`) header in any
  `_audit/results/**/review-*.md` MUST map to exactly one registry entry whose:
  - `id` matches,
  - `source` references the originating review file,
  - dependency paths are valid (the checker resolves each cited path against the repo),
  - and the `id` is unique (no collision with an unrelated entry).
- The checker fails on: a review id with no registry entry, a registry entry whose
  `source` does not match the review that introduced it, an invalid dependency path
  (e.g. `_retry.py` when the file is `retry.py`), or a duplicate id across unrelated
  subjects.
- This closes the AUFG-01-01 metadata errors and the AUFG-01-03/AUFG-01-08 collision
  class.

### Enforcement phasing

- Both ship **warning-only** for one baseline cycle (per ADR-047's ratchet discipline),
  then **ratchet to blocking** once current drift (AUFG-01-01 metadata, AUFG-01-02
  residual, `INDEX.md:126`) is resolved by Stage 3.

---

## Rationale

ADR-047's thesis — that governance artifacts must cross-validate rather than be manually
reconciled — is correct but incomplete: it ensured findings *have* lifecycle entries, not
that those entries are *consistent* with their sources or that derived status prose
*agrees* with the SSOT. P3 and P5 close the two remaining reconciliation gaps using the
same status-bearing, modular-checker pattern ADR-041/047 already proved. Option C
(generation) is the strongest drift prevention but disproportionate; Option B leaves
long-form docs authorable while making their *status claims* checkable.

---

## Consequences

**Positive:**
- Doc↔registry status drift becomes CI-visible (P3); review↔registry metadata errors and
  id collisions become CI-visible (P5).
- A single status SSOT is now defensible: derived docs cannot silently contradict it.

**Negative / Trade-offs:**
- Free-text status reconciliation needs a vocabulary + allowlist (ongoing, small).
- P5 depends on a stable `### [AUFG-XX-YY]` header convention in reviews (already
  established by ADR-047).
- Initial warning-only phase before blocking (ratchet discipline).

**Constraints introduced:**
- **SSOT (CONSTRAINTS.md §8):** AUFG lifecycle status is authoritative in the registry;
  derived docs reconcile or fail.
- **RULE-22:** cross-artifact status coherence is checked, not asserted.

---

## Deferred follow-ups — P4 and P6 (reasoned recommendation)

### P4 — health↔adoption reconciliation — **defer** (no new ADR now)

The structural mismatch between `governance-health` status and `configuration-adoption`
status largely self-corrected through real remediation work, and the *residual*
contradictions are a subset of what P3's doc↔status-SSOT checker already covers (status
prose contradicting the SSOT). A dedicated P4 ADR would duplicate P3's mechanism before
P3 has a baseline. **Recommendation:** track P4 as an `accepted_enhancement` follow-up;
revisit after P3 is blocking — if a health↔adoption-specific contradiction class remains
that P3 does not catch, promote it to its own ADR then.

### P6 — graph-grounded "adopted" proof — **fold into ADR-061, defer as a phase**

Graph-grounded proof that an `adopted` setting is truly consumed at its runtime boundary
is the *preferred* verification strategy of ADR-061's P1 measure (Option B.1). P6 is
therefore not a separate decision — it is the graph-grounded path *within* ADR-061's P1,
landing after the evidence-manifest fallback (Option B.2) establishes the baseline.
**Recommendation:** do not create a separate P6 ADR; ADR-061's Implementation Notes
already scope graph-grounded verification as the target end state for P1.

---

## RULE-XX Compliance

| Rule | Status | Note |
|------|--------|------|
| RULE-22 | ✅ | Cross-artifact status/metadata coherence is checked (P3, P5). |
| SSOT §8 | ✅ | Registry/matrix authoritative; derived docs reconcile or fail. |
| RULE-04/06/07 | ✅ | Modular, single-purpose checkers; file/structured-data only. |
| RULE-10/11 | ✅ | Failures testable and visible; no silent drift. |

---

## Implementation Notes (Stage 3 — Platform; NOT done by this ADR)

- Likely home: extend `scripts/governance/` (e.g. `_status_consistency.py`,
  `_review_registry_link.py`) wired into `scripts/check_governance_health.py` / CI.
- Reuse `scripts/governance/review_findings.py` for `### [AUFG-…]` parsing; reuse
  ADR-041 doc-drift machinery where it fits.
- P3 needs a `status_vocabulary.yaml` (contradiction table + allowlist).
- Tests: `tests/unit/scripts/governance/` — status-contradiction cases, missing/mismatched
  registry links, invalid dependency paths, id-collision cases.

**ADR Implementation Completeness Gate (Gate 12):** both checkers warning-only with a
clean baseline before ✅ Implemented; ratchet to blocking in a follow-up.

---

## Review Trigger

- After the first full review cycle with P3/P5 at blocking severity.
- If the `### [AUFG-XX-YY]` review convention changes.
- If P4/P6 promotion criteria (above) are met.
