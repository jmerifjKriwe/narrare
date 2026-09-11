# ADR-085 — KB Entity Resolution Layer

> **Status:** 🔄 Proposed (design; no implementation in this ADR)
> **Date:** 2026-09-07
> **Deciders:** Architecture Agent (draft), PO (pending)
> **Detailed design:** `docs/superpowers/specs/2026-09-07-kb-entity-resolution-design.md`
> **Related:** ADR-083 (benchmark program — Decision 9 inventory check applies),
> ADR-021 (deterministic analysis strategy — tiered hybrid pattern),
> ADR-054 (merge prompt Mode-1 governance, reused unchanged),
> ADR-080 (in-process asyncio boundary)

---

## Context

Benchmark runs `2026-09-07-clean-incremental-1..3` proved a production defect in
the KB extraction pipeline: under LLM variance the model sometimes emits
`new_entity` ("Anna Meyer", ch-04+) instead of `update_entity`+rename on an
existing entry ("Anna", ch-01–03), and the two coexist as separate KB entries.
Facts and relationships split across the duplicates poison every downstream
consumer (hybrid search, graph, suggestions, writing context). Run -3 measured
the blockage directly: relation coverage stuck at 0.2222 because 6
direction-fixable edges were entity-blocked by the "Anna"/"Anna Meyer"
duplicate.

The apply path is deliberately blocking-only
(`kb/_extraction_resolution.py`: exact-name or validated-ID match, never a
fuzzy merge). That invariant is correct and stays — but it means nothing ever
reconciles the duplicates after creation. The existing KB-009 machinery
(`router_merge.py` + `KBMergeService`/`KBMergeAgent`) is an LLM *adjudicator*
over caller-supplied pairs: it has no detection, no execution, and its router
is unmounted (404; benchmark inventory finding in-F1 / register Finding 3).

The corpus contains a **designed distractor**: "Anna Meier" (ch-09) — a
different person whose name is nearly identical to "Anna Meyer". Pure name
similarity *cannot* distinguish duplicate-of from different-person. The
distinguishing signals are temporal (handoff vs co-existence), attribute
continuity, and relationship-neighborhood overlap.

---

## Decision Drivers

- **Root cause, not symptom** — the defect is the *missing reconciliation
  stage*, not the model variance (variance is inherent; the system must be
  robust to it). Two×why: duplicates persist because apply is blocking-only by
  design; that design is right, therefore a separate post-hoc detection+merge
  stage is the missing half.
- **Distractor safety** — no name-only merge decision may ever execute; the
  Anna-Meier trap must be structurally rejected, not probabilistically hoped away.
- **Benchmarkability** — ADR-083 D3: only production REST/SSE surface is
  measurable. Detection quality must be consumable via endpoints the UI also
  drives, with a deterministic core (measurement validity — no LLM in the
  detection metric).
- **Inert by default** — the layer must not change any existing behavior for
  users who never invoke it; no auto-mutation of KB state without an explicit
  endorsement call.
- **No new infrastructure** — asyncio in-process; no new dependencies
  (edit distance via stdlib `difflib`); no new DB columns unless unavoidable.
- **Existing-pattern reuse** — analyzer+cache+service+router shape
  (`consistency_*`, `improve_*`), merge-not-clobber semantics, embedding
  search, dismissed-suggestions pattern.

---

## Options Considered

### Option A — Inline fuzzy guard at apply-time

Route `new_entity` items through a similarity check in
`apply_new_entity_item` and convert high-confidence duplicates to updates.

**Rejected.** Reverses the tested blocking-only invariant of the apply path;
per-item scope lacks the cross-entry context (neighborhoods, provenance
history) the distractor discrimination needs; a wrong inline decision mutates
data with no human gate; folds detection into CAP-IN-01 so the benchmark
cannot measure it as a capability; does not reconcile the already-duplicated
backlog the benchmark exposed.

### Option B — Mount KB-009 `router_merge.py` as-is (LLM-only resolution)

Mount the existing route; let callers (UI, benchmark) supply candidate pairs.

**Rejected as the primary layer.** Detection — the actual missing capability —
stays absent (callers must already know the duplicates); LLM-only judgment on
name-similar pairs is exactly what the distractor is designed to fool; the
prompt receives no provenance/neighborhood data the deterministic signals use;
non-deterministic core would make benchmark detection metrics noise. The LLM
adjudicator survives as a *service* consumed by the uncertain band (D7).

### Option C — Benchmark-only union binding (fix scoring, not the product)

Extend `benchmark/scoring/entity_match.py` to union-bind alias-matching
entries onto one reference entity; ship no product change.

**Rejected.** Measures *around* the defect: entity-coverage numbers improve
while the real KB stays poisoned for actual consumers (graph, search, writing
context). Violates the program's purpose (ADR-083 — findings must change the
product through the normal process, not the instrument).

### Option D — Deterministic detection engine + suggestion/endorse flow (chosen)

A pure, deterministic Core scoring engine (name tiers + temporal provenance +
attribute continuity + neighborhood overlap + embeddings) behind a new
`kb/entity_resolution/` app sub-module, exposing analyze/list/endorse/reject
endpoints; merges execute only on explicit endorsement; LLM adjudication
optional for the uncertain band.

**Pros:** distractor-safe by construction (veto semantics, name-only ceiling);
deterministic core → measurable detection precision/recall; inert by default;
reconciles backlog duplicates; apply path untouched.

**Cons:** more moving parts than A/B (engine + analyzer + executor + router);
provenance requires an additive apply-request field (D6); v1 has no automatic
cleanup (explicit endorsement only — deliberate).

---

## Decision

**We choose Option D**, in seven decisions:

1. **Two-layer architecture, pure Core engine.** All duplicate scoring is a
   pure, deterministic function over entry *snapshots* in
   `packages/core/narrare_core/kb/resolution/` (models, name tiers, signals,
   scoring — mirroring the benchmark `relation_predicates.py` RULE-04 split).
   App-layer orchestration (snapshot assembly, caching, persistence, LLM band,
   merge execution, HTTP) lives in `apps/api/narrare/kb/entity_resolution/`.
   The apply path stays blocking-only — its documented invariant is unchanged.

2. **Signal combination with veto semantics; co-existence vs handoff is the
   distractor discriminator.** Five signals (S1 name tier, S2 temporal
   provenance, S3 attribute continuity, S4 neighborhood overlap, S5 embedding
   similarity) with fixed weights; hard vetoes (contradiction, co-existence
   with distinguishable names) cap confidence below the suggestion band;
   a name-only ceiling prevents any name-similarity-only suggestion from
   reaching the actionable band. Confidence, bands, and calibration constants
   are specified in the design spec.

3. **Suggestions-only action policy in v1; no auto-merge execution exists.**
   The engine reports an `auto_merge_eligible` band (benchmark-measurable,
   future policy input), but v1 executes merges **only** via the explicit
   endorse endpoint. Nothing mutates KB state without an explicit call —
   inert by default, mechanically neutral for non-users.

4. **Merge = deterministic executor with deactivation, not deletion.**
   Deterministic survivor selection; fuller-name preservation (reusing the
   `decide_rename` downgrade guard); two-sided merge-not-clobber with conflict
   recording; relationship re-pointing with unique-constraint dedupe; loser
   entries deactivated (`status='deprecated'` + `metadata.resolution` audit
   block), never deleted — reversible, referentially safe, provenance-
   preserving. Idempotent on re-execution.

5. **Own endpoint surface; `router_merge.py` retired.** Novel-scoped
   `/novels/{novel_id}/kb/resolution/{analyze, suggestions,
   suggestions/{id}/endorse, suggestions/{id}/reject}`. The unmounted
   KB-009 router is deleted in the slice that wires resolution;
   `KBMergeService` survives as the internal uncertain-band adjudicator
   (service-to-service, no route). Inventory finding in-F1/F3 is resolved as
   *superseded by CAP-IN-10* (ADR-083 D9 same-change inventory update).

6. **Provenance via reserved JSONB key; no migration.** `ApplyExtractionRequest`
   gains an optional backward-compatible `chapter_id`; the apply flow stamps a
   reserved `metadata["provenance"]` block (chapters, first/last-seen,
   name variants) and strips that key from LLM-proposed content (proposals
   cannot forge provenance). No new columns (RULE-14 avoided); entries without
   provenance degrade to unknown-signal, never negative.

7. **LLM only in the uncertain band, through existing governed machinery.**
   Mid-band suggestions may be annotated by `KBMergeService`/`KBMergeAgent`
   via the existing Mode-1 governed merge prompt (RULE-01b/02/02a/02b paths
   unchanged). The deterministic core carries no LLM call; detection metrics
   never depend on it.

---

## Rationale

The distractor makes name similarity unusable as a decision basis — so the
chosen design's central move is to make *time* do the discriminating work:
a duplicate is born as a handoff (one entity's extraction trail ends where
the other's begins), while a different person co-exists as a second active
referent. That signal (plus attribute continuity and neighborhood overlap as
corroborations, and contradiction/co-existence as vetoes) is deterministic,
explainable per suggestion, and benchmark-falsifiable. Option A would have put
this judgment where the context is missing and the blast radius is maximal;
Option B would have delegated it to the component the distractor was designed
to defeat; Option C would have hidden the defect behind a better score. The
endorsement-only action policy trades automation for auditability in v1 —
the right trade while the calibration constants have exactly one validated
corpus, with the auto-band reported so the benchmark can earn (or refute) the
auto policy later.

---

## Consequences

**Positive:**

- The benchmark-proven duplicate defect gets a product fix measured by the
  program that found it: detection precision/recall vs the reference alias
  mapping (distractor = the precision test), merge execution = endorse →
  re-score (entity coverage rises, blocked relations unblock).
- Downstream consumers (graph, search, writing context) heal through one
  merge path with a full audit trail; merges are reversible (deactivation).
- The unmounted-surface inventory debt (KB-009) is retired rather than
  papered over.

**Negative / Trade-offs:**

- Two new modules (Core engine + app sub-module) and one additive API field;
  the first sub-package inside `kb/` (justified: 60+ flat files; cohesive
  vertical feature — flat-prefix rejected as worsening navigability).
- v1 does not auto-clean; users/benchmark must endorse. Accepted: inertness
  and measurement validity outrank convenience before calibration evidence.
- Provenance exists only for entries created after D6 ships; backlog entries
  score with degraded temporal signal (documented limitation).
- Deprecated-but-present loser entries require a documented visibility policy
  for listings/graph (spec verification checklist).

**Constraints introduced / touched:**

- RULE-03 (contracts first — `entity_resolution/contracts.py` + Core Protocols
  before any implementation), RULE-04 (sub-package split; file limits),
  RULE-05/06/07 (one-way deps; one responsibility), RULE-08 (no new deps —
  stdlib `difflib`), RULE-10 (per-slice tests), RULE-11 (every skip/veto
  logged and reported, never silent), RULE-12 (thin router), RULE-14
  (explicitly avoided — JSONB provenance), RULE-17 (types land with the
  endpoint slice), RULE-19 (`SessionDep` factories), RULE-20 (each phase is
  complete behavior; auto-merge execution is *absent*, not half-built),
  RULE-22 (LLM band rides the existing invocation-evidence path).
- ADR-083 D9: capability inventory + corpus assumptions updated in the same
  change as the endpoint surface (CAP-IN-10; driver apply payloads carry
  `chapter_id`).

---

## Implementation Notes

- **Binding detailed design:** module boundaries, Protocol-level contract
  signatures, signal definitions with confidence semantics and calibration
  constants, worked corpus examples (Anna-duplicate vs Anna-Meier-distractor),
  merge semantics, endpoint surface, benchmark integration (CAP-IN-10,
  expected-pair derivation, metrics), and the phased rollout with per-phase
  gates live in
  `docs/superpowers/specs/2026-09-07-kb-entity-resolution-design.md` (§1–§10).
- **Phasing:** P1 pure engine (inert) → P2 provenance stamping → P3 detection
  surface → P4 merge execution + retire KB-009 router → P5 LLM band → P6
  benchmark integration. Auto-merge policy is out of v1 entirely.
- **Suggestion identity is stateless:** deterministic id = hash of the ordered
  entry-id pair; endorse/reject re-derives and re-validates the pair score —
  no new suggestion table, no stale persisted state, no migration.
- **Verification items for implementing slices** (spec §9): metadata-template
  validation must admit the reserved `provenance` key; chapter position
  resolution via `ChapterRepository`; listing/graph visibility of deprecated
  entries; `ApplyExtractionRequest.chapter_id` backward compatibility.

**ADR Implementation Completeness Gate (Gate 12):** this ADR reaches
"✅ Implemented" only when phases P1–P6 are each fully wired, tested, and
referenced from their slices; the inventory update (P6) is part of the gate.

---

## Review Trigger

- [ ] After the first benchmark run with CAP-IN-10 (detection P/R measured):
      recalibrate the spec §4 constants; decide the auto-merge policy
      (default-off setting on `ProjectSettings`, ADR-069 precedent) — its own
      ADR-amendment if activated.
- [ ] When a second corpus/variant is authored: re-validate the handoff-gap
      and co-existence thresholds against it.
- [ ] If extraction-prompt work (v1.9.x+) reduces duplicate creation
      measurably, re-justify P2 provenance breadth — detection stays
      regardless (backlog + variance never hits zero).
- [ ] When frontend consumption is scheduled: RULE-16/17 slice (types + i18n
      namespace) must reference this ADR.
