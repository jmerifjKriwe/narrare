# ADR-075 — Series Foundation (SERIES-001 — Spec 1: Foundation + KB Evolution)

> **Status:** ✅ Implemented (implemented 2026-07-29 across all layers + committed; commit range `46a5c425`→`37f0cc17` — Core → Backend → Frontend, 26 commits over 5 vertical slices. Originally Accepted 2026-07-29 — user approved the design spec after a 6-question brainstorming session, then directed the coordinator to proceed to plan execution.)
> **Date:** 2026-07-29
> **Deciders:** Architecture Specialist; User (approved the design spec synthesised from a brainstorming session)
> **Supersedes:** —
> **Related:**
> ADR-074 (Author Voice Storage — the **predecessor** that documented the Series gap + the partial-close Review Trigger this ADR closes),
> ADR-055 (character-voice storage — descriptive/metric boundary pattern this ADR's Series-Settings mirror is consistent with),
> ADR-069 (`AdaptiveSettings` on `ProjectSettings` JSONB — the nested-settings pattern `SeriesSettings.author_voice` mirrors for forward-compat with Spec 3),
> ADR-011 (content versioning — the additive-schema migration discipline this ADR follows),
> CONSTRAINTS.md RULE-03/04/05/06/07/11/14/22,
> CR-04 (cross-feature coherence — the KB consumers verified compatible)

> **Scope of this ADR:** the **Series / Reihe Foundation** — the Series entity,
> the `Novel.series_id` containment, the hybrid Knowledge-Base scope model
> (Series-Canon + Novel-Overlay), the schema representation (2A + STI), the
> join-migration policies, the navigation model, and the multi-series policy.
> Series **Generation Context** (Spec 2), **Series Voice Hierarchy** (Spec 3 —
> closes the Voice-Teil of ADR-074's Review Trigger), **Cross-Novel Drift**
> (Spec 4), and **Series Export** (Spec 5) are **downstream program work**,
> flagged here but not designed here. This ADR defines the foundation those
> specs build on.

---

## Context

### Why this ADR exists

ADR-074 — in its §„Volume ≠ Series" finding and §„Series / Reihe is the NEXT
major platform-level feature" — recorded that **Narrare had no Series concept**.
Every novel was an isolated unit with its own Knowledge Base. A multi-book
series was therefore several disconnected projects: the magic system was
re-defined in every band, canonical character bios drifted between books, and
there was no structural connection between them.

> *"Narrare has NO series / Reihe concept today. Each novel is an isolated unit
> with its own Knowledge Base."* — ADR-074 §Volume ≠ Series

ADR-074 deliberately scoped author-voice storage at the **novel** level and
carried the Series question as a Review Trigger:

> *"When the Series / Reihe feature is designed — revisit the voice resolution
> model …; add the sibling `SeriesSettings.author_voice` home …"* — ADR-074 Review Trigger

**This ADR is that Series feature.** It closes the storage portion of ADR-074's
Review Trigger (the `SeriesSettings.author_voice` sibling home now exists, empty
in Spec 1 for Spec 3 to populate) and records every foundational decision the
brainstorming produced. The Voice-Teil (resolution model, blend/cascade policy)
remains open for Spec 3 — tracked in this ADR's own Review Trigger.

### Verified state (grounded, not assumed — per architectural-discipline §7)

| Concern | State | Location |
|---------|-------|----------|
| `Volume` model | EXISTS — `novel_id ForeignKey("novels.id", ondelete="CASCADE")`. Volume is a **child of Novel** (intra-novel chapter grouping). **NOT a series.** | `apps/api/narrare/volumes/models.py:19` |
| `Series` entity / `Novel.series_id` | **DID NOT EXIST** before this ADR — now created (migration `0037`). | `apps/api/narrare/series/models.py`, `apps/api/narrare/novels/models.py` |
| `KBEntry` binding | Was strictly `novel_id` (`nullable=False`, `ondelete="CASCADE"`). Harry Potter in book 1 and book 2 were two fully disconnected rows. Now `novel_id` is nullable + scope-discriminated. | `apps/api/narrare/kb/models.py:42-49` |
| Established per-entity JSONB-settings pattern | EXISTS — `AdaptiveSettings` + `author_voice` live as dedicated JSONB columns on `ProjectSettings`. The sibling `SeriesSettings.author_voice` mirrors this. | `apps/api/narrare/settings/models.py`, ADR-069/074 |
| KB consumer surface (CR-04) | ~15 modules import KB types; the STI is non-breaking via re-exports (mirrors ADR-074's voice-type extraction). | `packages/core/narrare_core/kb/schemas/` |

### Program-level decomposition (Series is a program, not a feature)

Series / Reihe is too large for one spec. It is decomposed into **5 sequential
specs**, each implemented before the next is brainstormed:

| # | Spec | Inhalt | Vorbedingung |
|---|------|--------|--------------|
| **1** | **Series Foundation + KB Evolution** *(this ADR)* | Series-Entity, `Novel.series_id`, KB Series-Canon+Novel-Overlay model, CRUD, navigation, UI | — |
| 2 | Series Generation Context | Series context for book N (state-at-(N−1) read-merge) | Spec 1 implemented |
| 3 | Series Voice Hierarchy | Override/Blend/Cascade for series base voice + novel nuances *(closes ADR-074 Review Trigger Voice-Teil)* | Spec 1 implemented |
| 4 | Series Cross-Novel Drift | ANAL-009 series-scope extension | Spec 1+2+3 |
| 5 | Series Export | Series manuscript / series bible / single-title | Spec 1 |

### Why Foundation + KB Evolution are ONE spec

Foundation (Series entity) and KB Evolution (character states across books)
are **not separable** into distinct specs, because:

1. **KB strategy determines the data model.** Whether a series shares a KB or
   keeps per-novel KBs with cross-references decides whether `KBEntry` needs an
   optional `series_id`.
2. **KB strategy determines the migration.** Shared KB = data movement.
   Per-novel KB with scope = pure schema extension.
3. **KB strategy determines all downstream cost.** Generation, Drift, Export,
   Voice — every KB consumer issues different queries depending on the strategy.

---

## Decision Drivers

- **RULE-03** — Contracts (`SeriesRepositoryProtocol`,
  `SeriesServiceProtocol`, `SeriesJoinServiceProtocol`) and the Core STI types
  MUST exist before the service/repository/UI is built.
- **RULE-04/06** — Modularise; one responsibility per file. The `series/`
  domain mirrors the `novels/` pattern; the KB scope logic gets its own
  `scope_repository.py` rather than bloating `repository.py`; STI lives in its
  own `kb/schemas/entry.py`.
- **RULE-05/07** — Core owns the Pydantic data contracts (`series/schemas.py`,
  `kb/schemas/entry.py`); Backend owns the repository + migration; no
  `core/`→`apps/` imports; dependency direction `router → service → repository → DB`.
- **RULE-11** — Graceful degradation: a standalone novel (no series) sees no
  scope UI; 404/409 errors are explicit, never silent `try/except: pass`.
- **RULE-14** — Every model change (`series`, `series_settings`, `Novel` columns,
  `kb_entries` columns) lands in ONE atomic Alembic migration (`0037`) with a
  working `upgrade()` + `downgrade()` — a model change without a migration is a
  build failure.
- **RULE-22 / CR-04** — The KB is shared data. Every KB consumer
  (ANAL-008/WRITE-010/ANAL-009, generation, consistency) must stay coherent
  after the schema change; the STI must be non-breaking.
- **ADR-074** — The `SeriesSettings.author_voice` sibling home is the
  forward-compat hook this ADR is required to add (closes the Series-storage
  portion of ADR-074's Review Trigger).
- **architectural-discipline §1/§4/§7** — Root-cause solution; no workarounds;
  "documented ≠ implemented" — the migration + modules + tests must actually
  land, the ADR only specifies them.

---

## Options Considered

### Decision 1 — KB strategy

**Option A — Per-Novel KB + identity layer.** Each novel keeps its own KB; an
identity layer links the "same" entity across books.
- **Rejected.** Duplicates the magic system / setting / world rules in every
  band → drift, sync effort, and a fragile identity resolution. Fights the
  heterogeneity of entity types (stable facts vs. evolving facts).

**Option B — Per-Series shared KB + snapshots.** A single KB per series;
novels see snapshots.
- **Rejected.** Breaks every existing KB query (`WHERE novel_id = X`) and the
  migration is a data move, not a schema extension. High blast radius (~15
  modules) for no gain over the hybrid.

**Option C — Hybrid: Series-Canon (shared, stable) + Novel-Overlay (per-band
state)** *(CHOSEN).* Heterogeneity-aware:
`system/concept/setting/location/object/timeline` (the majority of facts) rarely
vary per band → live in Canon; `character/faction` (the minority) evolve strongly
per band → live in Overlay. Respects the actual structure of the data.

### Decision 2 — Schema representation

| Option | Physical | Logical | Read-path | Blast radius |
|--------|----------|---------|-----------|--------------|
| Pure 2A | single table | NULL discriminator | simple | small |
| Pure 2B | two tables | separate types | UNION / 2 queries | large (~15 modules) |
| **2A + STI** | single table | discriminated Pydantic types | simple | small |

**Pure 2A** *(rejected)* — loses type safety (Canon vs Overlay are the same type).
**Pure 2B** *(rejected)* — type safety is real but the read-path UNION, the
cross-table relationships, and the blast radius outweigh it.
**2A + STI** *(CHOSEN)* — keeps 2A's small blast radius (single physical table,
non-breaking migration, additive columns) **and** recovers 2B's type safety via
discriminated Pydantic types (`SeriesKBEntry`, `NovelKBEntry`) in Core. The
physical DB enforces the invariant via a CHECK constraint; the application layer
enforces it via Pydantic STI. Double protection.

### Decision 3 — Navigation

**N1 — Flat-grouped (series as a dashboard grouping).** *(Rejected.)* Specs 2–5
all need a home for series-level UI (generation settings, voice, drift, export).
N1 would force ad-hoc locations for every later spec — probably embedded in
arbitrary novels.

**N2 — Series as a first-class Workspace with tabs.** *(CHOSEN.)* Gives every
later spec a coherent home from day one: `/series/[id]` with 4 tabs
(Bände, Canon KB, Settings, Voice-placeholder). Segments (not query params) for
shareability/bookmarks.

### Decision 4 — Multi-series membership

**Single-Series in Spec 1** *(CHOSEN.)* — a novel belongs to at most one series.
**Crossover** *(rejected as YAGNI.)* — a novel in multiple serieses has no
consumer, no spec, no demand. The migration path to a join-table is known and
documented (see Risks) but deliberately not pre-built.

### Decision 5 — Scope-default policy for new entries (Policy iii)

Entity-type-based default scope for new KB entries in series-novels:
`system/concept/setting/location/object/timeline → Series-Canon`;
`character/faction → Novel-Overlay`. The user can override per entry via the
ScopeToggle. *(CHOSEN — matches the KB-type heterogeneity that drove Option C.)*

### Decision 6 — Join migration policy (Policy α)

**Adaptive scope assignment when a novel joins a series:**
- If the target series' Canon is **empty**: Policy iii heuristics apply — the
  joining novel's stable-fact entries are promoted to Canon, evolving entries
  stay Overlay.
- If Canon is **non-empty**: all of the joining novel's entries stay
  Novel-Overlay (the series already has its canon; the novel is a guest).

The heuristic plan is shown to the user in a **Preview** step before Apply runs,
so the user sees and can reason about the assignments. *(CHOSEN — predictable
for the common cases, transparent via Preview, reversible via ScopeToggle.)*

---

## Decision

**Option C + Schema 2A+STI + N2 + Policy iii + Policy α + Single-Series.**

- A **`Series`** entity (with `SeriesSettings` 1:1 sibling) groups novels.
  `Novel.series_id` (nullable, `ON DELETE SET NULL`) attaches a novel to a
  series; deleting a series makes its novels standalones.
- A single physical **`kb_entries`** table holds both layers, discriminated by
  a DB CHECK (`ck_kb_entries_scope_invariant`) and by Core STI types:
  - **Series-Canon** — `novel_id IS NULL`, `series_id` set, `base_entry_id NULL`.
  - **Novel-Overlay** — `novel_id IS NOT NULL`, `series_id` set iff the novel is
    in a series, optional `base_entry_id` link to a Canon entry it overlays.
- **`SeriesSettings.author_voice`** JSONB column is added **empty** in Spec 1 —
  the forward-compat hook for Spec 3 (closes the Series-storage portion of
  ADR-074's Review Trigger).
- **Navigation:** `/series/[id]` workspace with 4 tabs.
- **Scope toggle** (promote/demote) is available per entry, confirmation-gated.

---

## Rationale

The hybrid Canon+Overlay model is the architecturally honest answer to the
**heterogeneity of KB entity types**. Stable facts (magic systems, world rules,
foundational artifacts) are duplicated and drift under Option A; evolving facts
(character arcs per book) are flattened under Option B. The hybrid lets each
fact live at the scope where it is actually stable — the same insight that
makes Policy iii's entity-type defaults correct.

Schema 2A+STI is the **proportionality** choice: Pure 2B's type-safety gain is
real but its read-path UNION and ~15-module blast radius are disproportionate to
a foundation spec. 2A+STI delivers the type safety at the application layer
(without re-exports — the discriminated union is additive to the existing
re-exported `KBEntry`) while keeping the physical change additive + nullable →
backward compatible.

Single-Series and N2 are **YAGNI + forward-fit**: Crossover has no consumer;
N2 gives every later spec a home without pre-building their internals.

### Sustainability check

1. **Correct in 3 months?** Yes — every later spec (Generation, Voice, Drift,
   Export) extends an additive foundation; none requires undoing Spec-1 work.
2. **Hard-to-undo coupling?** Minimal — additive columns, one atomic migration
   with a downgrade, STI is additive to the re-exported union. A standalone
   novel sees no scope UI; `WHERE novel_id = X` queries return exactly what they
   returned before (Canon rows have `novel_id IS NULL` and are excluded).
3. **Simplest correct solution?** Yes — one table, one migration, one workspace.
   Pure 2B would be more general but less correct for the actual feature scope.
4. **Design intent clear?** Yes — `series/`, `kb/scope_repository.py`,
   `kb/canon_service.py` each name their single responsibility.

---

## Consequences

**Positive:**

- **Unblocks Specs 2–5.** Generation can call `find_merged_for_novel()`; Voice
  has its `SeriesSettings.author_voice` home; Drift can extend ANAL-009;
  Export has a series container.
- **One coherent KB scope model.** Canon + Overlay, enforced physically (CHECK)
  and logically (STI). RULE-22 coherence.
- **Additive, backward-compatible migration.** Existing novels get
  `series_id=NULL`; existing KB queries are unchanged (regression-tested).
- **Type-safe at the application layer** without a two-table read-path cost.
- **Closes the Series-storage portion of ADR-074's Review Trigger.**

**Negative / Tradeoffs:**

- One atomic Alembic migration touches three tables (`series`,
  `series_settings`, `novels`, `kb_entries`) — accepted; standard foundation
  cost, and `upgrade()` + `downgrade()` are regression-tested (RULE-14).
- The `novel_id IS NULL` semantics for Canon require discipline — a stray
  `WHERE novel_id = X` will silently exclude Canon (which is the *desired*
  behaviour for existing consumers, but new series-aware consumers must use the
  scope repository methods, not raw queries).
- **`~15 KB-consumer modules need verification** — mitigated by the STI being
  additive to the re-exported `KBEntry` union and by regression tests for
  ANAL-008/WRITE-010/ANAL-009.
- Crossover (a novel in multiple serieses) would require a join-table migration
  later — **deliberately deferred** (no consumer).

**Constraints introduced:**

- Series-aware KB access MUST go through `KBScopeRepository`
  (`find_canon_for_series` / `find_overlay_for_novel` / `find_merged_for_novel`),
  not raw `WHERE novel_id = …` — the analogue of ADR-050's "no SSOT bypass".
- A new `KBEntry` subtype MUST preserve the scope invariant (`scope` field
  matches the DB CHECK). The STI is the single place the discrimination lives.
- Canon/Overlay toggles MUST be confirmation-gated (both have side effects beyond
  the current entry).

---

## CR-04 Cross-Feature Impact (coherence)

The KB is **shared data** — read by generation, by analysis (ANAL-008/WRITE-010/
ANAL-009), by consistency, and now by Series scope logic. This ADR requires
coherence end-to-end, not feature-local:

- **Producer (Series CRUD / Join / Scope toggle).** Writes Canon (via
  `KBCanonService`, `KBScopeRepository.promote_to_canon`) and Overlay
  (`demote_to_overlay`). Join runs Policy α heuristics atomically.
- **Consumer (generation read path) — future (Spec 2).** Will call
  `find_merged_for_novel(novel_id)` to assemble Canon + latest-Overlay. The
  method EXISTS and is tested in Spec 1 (pre-built for Spec 2).
- **Consumers (existing KB readers — ANAL-008/WRITE-010/ANAL-009).** Verified
  compatible via the backward-compat regression test
  (`test_backward_compat_scope_change.py`) — existing `WHERE novel_id = X`
  queries return the same result set as before the schema change (Canon rows
  are excluded by their `novel_id IS NULL`).

This is the CR-04 lesson (architectural-discipline §7): the schema change is
defined together with its consumer impact. Because Canon is **new data**
(`novel_id IS NULL`), the cross-feature surface is **additive** — no existing
consumer sees Canon unless it asks for it — but the scope-invariant boundary is
fixed **here**, so the first series-aware consumer cannot accidentally mix layers.

---

## Retrofit-Plan

> **Scope note.** This ADR defines the foundation. It does NOT itself wire
> Series into generation, voice, drift, or export — those are Specs 2–5, each
> with its own Retrofit-Plan when it lands. The migration + module creation is
> therefore the Retrofit-Plan focus.

### 1. Inventory of affected paths (foundation)

Backend — **new** `apps/api/narrare/series/` domain (mirrors `novels/`):
- `models.py` — `Series`, `SeriesSettings` SQLAlchemy.
- `contracts.py` — `SeriesRepositoryProtocol`, `SeriesServiceProtocol`
  (RULE-03 — defined before implementation); `join_contracts.py` —
  `SeriesJoinServiceProtocol` (extracted for RULE-04, mirrors the
  `kb/scope_contracts.py` split — see Post-Implementation Amendment §B).
- `schemas.py`, `repository.py`, `service.py` (CRUD + status transitions),
  `join_service.py` (Policy α preview/apply), `router.py`, `router_novels.py`,
  `dependencies.py`.

Backend — **KB scope additions** in `apps/api/narrare/kb/`:
- `scope_repository.py` — `KBScopeRepository`:
  `find_canon_for_series`, `find_overlay_for_novel`, `find_merged_for_novel`,
  `promote_to_canon`, `demote_to_overlay`.
- `scope_contracts.py` — `KBCanonServiceProtocol`, `KBScopeServiceProtocol`,
  `KBScopeMutationProtocol` (RULE-03 — added post-PR-#145 review; see §B).
- `canon_service.py` — `KBCanonService` (Canon CRUD).
- `router_canon.py` — Canon CRUD endpoints; `router_scope.py` — promote/demote.
- `models.py` — `series_id`, `base_entry_id` columns; partial unique indexes
  (`uq_kb_canon_per_series`, `uq_kb_overlay_per_novel`); CHECK
  `ck_kb_entries_scope_invariant`.

Backend — **modified** `apps/api/narrare/novels/models.py` — `series_id`,
`series_position`, `subtitle`.

Core — **new** `packages/core/narrare_core/series/schemas.py` — `Series`,
`SeriesSettings` Pydantic (pure, no HTTP/DB).

Core — **new** `packages/core/narrare_core/kb/schemas/entry.py` — STI:
`KBEntryBase`, `SeriesKBEntry`, `NovelKBEntry`, discriminated union `KBEntry`.

Alembic — `apps/api/alembic/versions/0037_series_foundation.py` — atomic
upgrade + downgrade (RULE-14).

### 2. Migration steps (5 vertical slices — each independently shippable)

1. **Slice 1 — Data Foundation:** `Series` + `SeriesSettings` SQLAlchemy +
   Alembic `0037` (tables + Novel columns) + Core `series/schemas.py`.
2. **Slice 2 — KB Scope:** `kb_entries` schema extension + `0037` KB steps +
   STI Core types (`entry.py`) + `KBScopeRepository` scope methods.
3. **Slice 3 — Series CRUD + Join-Flow:** Backend services + CRUD router +
   Join-with-Preview (Policy α) + Policy iii heuristics + scope-toggle endpoints.
4. **Slice 4 — Frontend Dashboard + Workspace:** Series/Standalone cards +
   `/series/[id]` workspace (4 tabs) + Bände-Liste + Settings-Form + i18n.
5. **Slice 5 — KB Scope UI:** ScopeToggle in KBEditor + Canon-Tab in the
   workspace + `kb.scope.*` / `series.canon.*` i18n (en/de/fr).

### 3. Breaking-change assessment

- **Schema change is additive + nullable** → backward compatible. Existing
  novels get `series_id=NULL`; existing KB rows keep their `novel_id`.
- **STI is additive to the re-exported `KBEntry` union** → every existing
  `from narrare_core.kb.schemas import KBEntry` import resolves unchanged.
- **`uq_kb_entries_novel_slug` → partial indexes** → the old single unique
  constraint is replaced by two partial indexes that preserve the original
  per-novel uniqueness for Overlay rows (`novel_id IS NOT NULL`) while allowing
  Canon rows (`novel_id IS NULL`) their own per-series uniqueness.
- **No production caller breaks** at the schema level. Series-aware consumers
  are additive (Spec 2+).

**Net: fully backward compatible (additive + re-exports + partial indexes only).**

### 4. Test update plan

- **Core STI tests** (`tests/unit/core/kb/schemas/test_entry.py`): subtype
  validation, discriminated-union dispatch, JSON round-trip, reject-mismatch.
- **Backend scope tests** (`tests/unit/api/kb/test_scope_repository*.py`):
  `find_canon/overlay/merged`, promote/demote round-trip, the backward-compat
  regression (`test_backward_compat_scope_change.py`).
- **Backend series tests** (`tests/unit/api/series/`): status transitions,
  join with empty/non-empty Canon, 404/409 handling, delete → standalone,
  atomicity.
- **Migration test** (`tests/integration/test_migration_0037.py`): upgrade +
  downgrade round-trip, partial indexes + CHECK present, existing rows readable.
- **Frontend tests** (Vitest): ScopeToggle hidden-when-standalone + confirm
  dialogs, CanonKBTab, SeriesWorkspace tab-routing, hooks.

---

## Risks Surfaced for Coordinator/User Decision (before/during implementation)

These are NOT blockers for this ADR; they are acknowledged and mitigated:

1. **KB schema change touches ~15 consumer modules.** Mitigated by the STI
   being additive to the re-exported union and by the backward-compat
   regression test. Low risk, verified green.
2. **Migration changes existing KB uniqueness semantics.** The old
   `uq_kb_entries_novel_slug` is replaced by partial indexes. Mitigated by the
   partial indexes preserving Overlay uniqueness exactly (`novel_id IS NOT
   NULL`) and by the migration round-trip test. Low risk.
3. **`novel_id IS NULL` Canon semantics need discipline.** New series-aware
   consumers must use the scope repository, not raw queries. Mitigated by the
   methods existing and the contract being fixed here. Medium risk (discipline).
4. **Policy iii heuristics may default wrongly for an edge entity.** Mitigated
   by the Preview step (user sees assignments before Apply) and by the per-entry
   ScopeToggle override. Low risk.
5. **Scope drift (Scope-1 adds Conflict-Detection "because it's close").**
   Mitigated by the binding YAGNI list; new features must be justified, not
   silently added. Medium risk (process).
6. **Perry-Rhodan edge case (1000 books) does not scale.** 1000 Canon entries
   + 1000×character Overlays are storage-trivial. Spec 1 is not the scaling
   point; Spec 2 (Generation) must address pagination/priority ranking. Low risk.

No decision required a user call beyond approving the design spec.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-03 | ✅ | `SeriesRepositoryProtocol` / `SeriesServiceProtocol` (`series/contracts.py`) + `SeriesJoinServiceProtocol` (`series/join_contracts.py`) + `KBCanonServiceProtocol` / `KBScopeServiceProtocol` (`kb/scope_contracts.py`) defined before implementation; Core STI types in `kb/schemas/entry.py` before the scope repository. (Post-PR-#145 split — see Amendment §B; the original single `series/contracts.py` is now three files for RULE-04.) |
| RULE-04 | ✅ | Modularised: `series/` domain mirrors `novels/`; KB scope logic split into its own `scope_repository.py` (not bloating `repository.py`); STI in its own `kb/schemas/entry.py`; join logic in its own `join_service.py`. |
| RULE-05/06 | ✅ | Core owns `series/schemas.py` + `kb/schemas/entry.py`; Backend owns repository + migration + service; one responsibility per file; the `series/` domain owns its own models, contracts, service, router. |
| RULE-07 | ✅ | Dependency direction `router → service → repository → DB`; Core data contracts have no `apps/` imports; the STI is additive to the acyclic KB schema read direction. |
| RULE-11 | ✅ | Standalone novel → no scope UI (graceful, not a crash); 404/409 explicit; no `try/except: pass`. |
| RULE-14 | ✅ | The `series` + `series_settings` + Novel columns + `kb_entries` columns all land in ONE Alembic migration (`0037_series_foundation`) with `upgrade()` + `downgrade()`, in the same task batch as the model changes. |
| RULE-22 / CR-04 | ✅ | Cross-feature coherence: the schema change is defined together with KB-consumer impact; the STI is non-breaking (additive to the re-exported union); the backward-compat regression test verifies ANAL-008/WRITE-010/ANAL-009 stay green; Canon is additive data no existing consumer sees unless it asks. |

---

## Post-Implementation Amendment (PR #145 Review — Contract & Integrity Fixes)

> The PR #145 review found that the Series Foundation's *implementation* diverged
> from its *contracts/spec* in several places. This amendment records the
> architecture-level corrections (the contracts/decisions are fixed here by the
> Architecture Specialist; Backend/Frontend/Platform implement against them).
> Architectural-discipline §7 ("documented ≠ implemented") applies — these were
> documented-but-not-implemented gaps, now closed at the contract layer.

### A. Ownership is enforced at the service boundary (C1 / IDOR)

`user_id` is now a parameter on every ownership-relevant method of
`SeriesServiceProtocol` (`series/contracts.py`),
`SeriesJoinServiceProtocol` (`series/join_contracts.py`),
`KBCanonServiceProtocol`, and `KBScopeServiceProtocol` (`kb/scope_contracts.py`).
The ownership semantic
mirrors the *already-correct* `KBCanonService._verify_series_ownership`: a
missing or not-owned resource raises `ForbiddenError` (403, anti-enumeration —
never 404). It is encoded as a documented Protocol contract (a private helper
per concrete service), NOT a separate `OwnershipVerifier` Protocol — consistency
with the established canon/novel pattern.

### B. Missing RULE-03 Protocols added (I-A1)

`KBCanonServiceProtocol` + `KBScopeServiceProtocol` are added in a new
`apps/api/narrare/kb/scope_contracts.py` (split from `contracts.py`, which sat
at its 197-line ceiling — RULE-04; mirrors the `context_contracts.py`
extraction). ADR-075's RULE-03 evidence is now complete and no longer
misleading.

### C. `list[Any]` → typed `NovelRow` (I-A2 / RULE-09)

`SeriesRepositoryProtocol.list_novels` now returns `list[NovelRow]`, a new
pure Core value object in `packages/core/narrare_core/series/schemas.py`. The
apps-layer `NovelSummaryResponse` is built FROM it (Core → apps, never reverse).

### D. Demote Canon-integrity guard (I-A3 / D4) — DECISION: implement the 409

**Option A (implement) chosen** over amending the spec to drop the guarantee.
Rationale: a Canon entry is shared across all novels of the series; if another
member novel relies on it as Canon (no same-slug Overlay of its own), demoting it
to a single novel's overlay silently removes it from that novel's merged view —
violating Canon integrity and RULE-11 (silent breakage). The 409 forces explicit
resolution. Behaviour contract specified in the PR #145 fix plan §D7.

### E. FK policy + overlay `series_id` (C2 / D6) — DECISION: `ON DELETE SET NULL`

`kb_entries.series_id` changes from `CASCADE` → `ON DELETE SET NULL` (one Alembic
migration edit — RULE-14). Combined with two invariants:

1. **Overlays never persist `series_id`** — it is derived from `novel.series_id`.
   `demote_to_overlay` clears `series_id`; `remove_novel` detaches it (a no-op
   on KB rows since overlays never carry it). This *amends* the original Decision
   text ("Novel-Overlay — `series_id` set iff the novel is in a series"): the
   redundantly persisted copy was the root cause of C2.
2. **`delete_series` deletes Canon rows in-transaction** (the Canon fate) — Canon
   rows have `novel_id IS NULL`, so they cannot survive `SET NULL` under
   `ck_kb_entries_scope_invariant`; the service makes the fate explicit.

Justification: symmetry with `novels.series_id` (SET NULL → standalone) makes the
FK itself the guarantee that Novel-Overlays survive a series delete, instead of a
load-bearing application `UPDATE`. Canon entries have no novel to fall back to, so
deletion is their correct fate.

### F. Stable `reason_code` for join treatments (C3)

`JoinReasonCode` (Literal: `entity_default_canon` / `entity_default_overlay` /
`canon_nonempty_overlay`) added to Core; `JoinEntryTreatment` gains
`reason_code` (machine-stable, i18n-resolvable) alongside the English `reason`
tooltip (kept for MCP/CLI — RULE-12). Fixes the frontend
`t(series.join.reason.${reason})` that could never resolve against free-form
English sentences.

> These corrections do not reverse Decision 1–6 (the Canon/Overlay hybrid,
> Schema 2A+STI, Policy α/iii stand). They tighten ownership enforcement, close
> RULE-03 gaps, and fix a data-integrity FK bug. RULE-21: the contract/FK changes
> are material and are recorded here; re-review is not required because this ADR
> amendment is the re-review artefact.

---

## Review Trigger

- [ ] When **Spec 2 (Series Generation Context)** is implemented — verify
      generation calls `KBRepository.find_merged_for_novel()` correctly (Canon +
      latest-Overlay merge, Overlay wins on slug collision) and that the token
      budget for the merged set is sane. *(This ADR pre-builds the method; Spec 2
      consumes it.)*
- [x] **Spec 3 (Series Voice Hierarchy) — CLOSED by ADR-078 (2026-08-05):** the
      voice model is resolved (**Delta** — series voice as foundation, novel voice
      additive, per-novel `use_series_voice` opt-out), the empty
      `SeriesSettings.author_voice` column is populated (reusing the existing
      `AuthorVoiceAgent` — no new agent), and **the Voice-Teil of ADR-074's Review
      Trigger is fully closed** (storage by this ADR, voice model by ADR-078).
      `{{author_voice}}` is extended (no new variable); `AuthorVoiceConsumer`
      renders the Delta composition. See ADR-078.
- [x] **Series-storage portion of ADR-074's Review Trigger — CLOSED by this ADR
      (2026-07-29):** the `SeriesSettings.author_voice` sibling home now exists
      (empty in Spec 1). ADR-074's novel-level home remains the primary scope
      (no forced cascade) — series voice is an additive sibling. See ADR-074.
- [ ] When **Spec 4 (Cross-Novel Drift)** is implemented — verify the
      series-scope read path (full-series scan vs current-vs-prior-band) and
      performance for long serieses.
- [ ] If **Crossover demand** materialises — migrate `Novel.series_id` (single
      FK) to a join-table; the migration path is known and additive.
- [ ] If **Policy iii defaults** prove wrong for a recurring entity type —
      adjust the heuristic (additive; user override already exists).

---

## Cross-References

- **ADR-074** — Author Voice Storage (the predecessor that documented the Series
  gap; this ADR closes the Series-storage portion of its Review Trigger; the
  Voice-Teil remains open for Spec 3).
- **ADR-069** — `AdaptiveSettings` on `ProjectSettings` JSONB (the nested-
  settings pattern `SeriesSettings.author_voice` mirrors for Spec 3).
- **ADR-055** — character-voice storage contract (descriptive/metric boundary
  pattern; the Spec-3 series voice should preserve it).
- **ADR-011** — content versioning (additive-schema migration discipline).
- `docs/superpowers/specs/2026-07-29-series-foundation-design.md` — the design
  spec this ADR is based on.
- `docs/features/series/SERIES-001-foundation.md` — the user-facing feature spec.
- `apps/api/narrare/volumes/models.py:19` + WRITE-011 — evidence for the
  Volume ≠ Series finding (carried forward from ADR-074).
