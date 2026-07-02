# FIND-014 — ADR-050 Not Implemented: CrossFeatureRefIndex.check_refs() Has No Production Consumer

> **Status:** `identified` (open)
> **Priority:** P1
> **Source:** CR-04 Cross-Feature Coherence (2026-06-30 re-review)
> **Related:** FIND-009 (ADR-044 half resolved; ADR-050 half overclaimed), ADR-050, CR-AUFG-04-10
> **Lifecycle:** `docs/development/finding-lifecycle.md` — `resolved` requires Design + Implementation + Enforcement

---

## Problem

ADR-050 is `✅ Accepted` but **NOT `✅ Implemented`** (Phase C/D pending per its
own Gate-12 text). The cross-feature ref-lifecycle contracts and the read-side
`CrossFeatureRefIndexImpl` exist and are wired into DI, but **no production
consumer calls `check_refs()`**. `ConsistencyOrchestrator` does not promote
`RefIntegrityIssue`s into typed `ConsistencyIssue`s via
`ContradictionPromotionPolicy`.

CR-00/CR-05 marked FIND-009 "✅ Resolved via ADR-044 + ADR-050". Per
`finding-lifecycle.md` that is only fully true for the ADR-044 half. The
ADR-050 half is `implemented` (contracts + impls + tests) but not yet `enforced`
through the consistency pipeline.

## Code References

- **ADR-050 status:** `docs/architecture/decisions/ADR-050-cross-feature-context-contracts.md:3` — `✅ Accepted` (not Implemented); Phase C/D pending at `:42-44`, `:786`.
- **check_refs() impl:** `apps/api/narrare/consistency/ref_index.py:78` — `CrossFeatureRefIndexImpl.check_refs()`.
- **DI wiring:** `apps/api/narrare/consistency/deps.py:98` — `get_cross_feature_ref_index` factory exists.
- **No production consumer:** grep for `check_refs` across `apps/api/narrare/` returns only the impl + tests (`tests/unit/api/consistency/test_cross_feature_ref_index.py`, `tests/unit/core/context/test_integration_contracts.py`). No router/service/orchestrator calls it.
- **ConsistencyOrchestrator:** `apps/api/narrare/consistency/consistency_orchestrator.py` — does not import or consume `CrossFeatureRefIndex` or `RefIntegrityIssueSink`.
- **ContradictionPromotionPolicy:** exists in Core (`packages/core/narrare_core/context/integration_contracts.py`) but is not applied in production.

## Impact

- Stale/deleted KB entity references (timeline events, chapter frontmatter, storyboard outlines) are **not surfaced as typed consistency issues** in the consistency pipeline.
- Users run consistency checks but ref-integrity problems (e.g., a chapter frontmatter referencing a deleted character) are silently absent from results.
- The "✅ Resolved" claim for FIND-009's ADR-050 half is an overclaim per `finding-lifecycle.md` §4 ("ADR Accepted → mark resolved" anti-pattern).

## Prioritized Remediation

1. **Wire `check_refs()` into the staged consistency pipeline (CR-AUFG-04-10):**
   - Extend `ConsistencyOrchestrator.run_staged_check()`/`stream_staged_check()` with a ref-integrity stage that calls `check_refs()` for registered consumers (`timeline`, `storyboard`, `chapter_frontmatter`).
   - Promote `RefIntegrityIssue`s to typed `ConsistencyIssue`s via `ContradictionPromotionPolicy` (error vs warning).
2. **Elevate ADR-050 to `✅ Implemented`:** update ADR-050 status line + Gate-12 checklist + INDEX.md.
3. **Register durable `CR-AUFG-04-*` lifecycle entries** in `docs/architecture/governance/aufg-registry.md`.
4. **Correct FIND-009 wording** in `cr-05-initial-findings.md`: "ADR-044 resolved; ADR-050 Phase C/D pending (CR-AUFG-04-10)".
5. **Add regression test** proving a stale/deleted KB ref surfaces as a typed `ConsistencyIssue`.

## Alternatives Considered

- **Declare FIND-009 fully resolved and close.** Rejected: ADR-050's own status says not Implemented; `check_refs()` has no consumer. This repeats the "ADR Accepted → mark resolved" anti-pattern.
- **Add per-feature workaround formatters.** Rejected: ADR-050 already specifies the correct pipeline integration; no new ad-hoc formatter is warranted.
