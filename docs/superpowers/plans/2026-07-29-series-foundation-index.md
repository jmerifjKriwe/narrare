# Series Foundation — Spec 1 Implementation Plan Index

> **For agentic workers:** This is the master index for the Series Foundation Spec 1 implementation plan. The plan is split across 4 files for reviewability and parallel execution. Read this file first.

**Goal:** Implement Series/Reihe Spec 1 (Foundation + KB Evolution) — Series entity, KB Series-Canon+Novel-Overlay scope model, CRUD, Navigation (N2 Workspace), UI. Spec source: [`docs/superpowers/specs/2026-07-29-series-foundation-design.md`](../specs/2026-07-29-series-foundation-design.md).

**Companion notes:** [`docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md`](../specs/2026-07-28-series-cross-spec-notes.md) — brainstorming-state notes, YAGNI list, notes for Specs 2–5.

**Architecture summary:** Hybrid KB (Option C: Series-Canon + Novel-Overlay) on single physical `kb_entries` table with discriminated Pydantic types (Schema 2A+STI). Series is a first-class object with its own Workspace (N2). Single-Series membership in Spec 1 (no Crossover).

---

## Plan Files (execute in order)

| # | File | Slice(s) | Status | Lines |
|---|------|----------|--------|-------|
| 1 | [`2026-07-29-series-foundation.md`](2026-07-29-series-foundation.md) | **Slice 1 (Data Foundation) + Slice 2 (KB Scope)** — Core schemas, SQLAlchemy models, Alembic migration, STI types, scope-aware repository methods | Ready | ~1578 |
| 2 | [`2026-07-29-series-foundation-slice-3-crud-join.md`](2026-07-29-series-foundation-slice-3-crud-join.md) | **Slice 3 (Series CRUD + Join Flow)** — contracts, repository, service, join_service (Policy α), router, dependencies, KB scope service + endpoints, Canon KB CRUD router | Ready | ~1100 |
| 3 | [`2026-07-29-series-foundation-slice-4-frontend.md`](2026-07-29-series-foundation-slice-4-frontend.md) | **Slice 4 (Frontend Dashboard + Workspace)** — TS types, API client, hooks (useSeries, useNovelSeries, useSeriesJoin), SeriesCard, dashboard mod, SeriesWorkspace + 4 tabs, Hero/BändeList/Settings/JoinPreviewDialog, i18n en/de/fr | Ready | ~1100 |
| 4 | [`2026-07-29-series-foundation-slice-5-kb-scope-ui.md`](2026-07-29-series-foundation-slice-5-kb-scope-ui.md) | **Slice 5 (KB Scope UI) + Final Doc Gate** — useKBScope, useCanonKB, ScopeToggle, KBEditor integration, CanonKBTab + CanonKBEditor, i18n kb.scope.*, ADR-075, SERIES-001, GLOSSARY, CURRENT_STATE, ADR-074 partial close | Ready | ~900 |

**Total:** ~4700 lines across 4 files.

---

## Execution Order & Dependencies

```
Slice 1+2 (Plan File 1)
   │
   │ Schema must exist before services can be built
   ▼
Slice 3 (Plan File 2)
   │
   │ Backend endpoints must be live before frontend consumes
   ▼
Slice 4 (Plan File 3)  ◄──── Can start once Slice 3's contracts/endpoints are reviewed
   │                       (doesn't need full Slice 3 implementation, just interfaces)
   ▼
Slice 5 (Plan File 4)  ◄──── Needs Slice 4's types/hooks pattern + Slice 3's scope endpoints
   │
   ▼
Spec 1 Complete → Spec 2 brainstorming begins
```

**Critical path:** Slice 1+2 → Slice 3 → Slice 4 → Slice 5 (linear). Total estimated time: ~3-5 days of focused implementation.

**Parallel opportunities:**
- Slice 3 Task 3.7 (KB scope service + endpoints) and Task 3.8 (Canon KB router) can run in parallel once Slice 3 Tasks 3.1-3.6 are done.
- Slice 4 Task 4.1 (types + API client) can start while Slice 3 is mid-flight (just needs the API contract, not full implementation).
- Slice 5 Task 5.1 (useKBScope) and Task 5.2 (useCanonKB) are independent.

---

## Per-Slice Success Criteria

| Slice | Definition of Done |
|-------|--------------------|
| **1+2** | Alembic 0036 applied; schema round-trip test green; STI types importable; `find_canon_for_series`/`find_overlay_for_novel`/`find_merged_for_novel`/`promote_to_canon`/`demote_to_overlay` implemented + tested; backward-compat regression test green (existing KB queries unaffected). |
| **3** | All Series CRUD endpoints live; join preview/apply two-step works end-to-end; Canon KB CRUD endpoints live; scope-toggle endpoints live; status-transition enforcement; 409 conflicts on novel-already-in-series; auth enforcement on all endpoints. |
| **4** | Dashboard shows mixed Series+Standalone cards; `/series/[id]` workspace renders with 4 tabs (Bände/Canon-placeholder/Settings/Voice-placeholder); JoinPreviewDialog shows per-entry treatments; up/down-buttons reorder works; i18n parity en==de==fr. |
| **5** | ScopeToggle renders conditionally (hidden for standalone novels); promote/demote with confirmation dialogs; Canon-tab placeholder replaced with functional CanonKBTab; `kb.scope.*` i18n complete. |
| **Final** | ADR-075 written + indexed; SERIES-001 feature spec written; GLOSSARY updated; CURRENT_STATE entry; ADR-074 Review Trigger partially closed. |

## Global Success Criteria (Spec 1 Complete)

- [ ] `just check` green (Architecture, Adoption, AI-UX, Frontend-Size, Streaming, Prompt-Structure, Doc-Drift)
- [ ] `just test` green (backend)
- [ ] `just test-frontend` green (frontend)
- [ ] Coverage: Core 90%+, Backend 85%+, Frontend 80%+, Migration 100%
- [ ] Regression: ANAL-008/WRITE-010/ANAL-009 voice-lane tests green (KB schema change didn't break them)
- [ ] i18n parity en==de==fr for all new namespaces
- [ ] No new architecture exceptions without ADR
- [ ] All Doc Gate artifacts committed (ADR-075, SERIES-001, GLOSSARY, CURRENT_STATE, ADR-074 partial close)

---

## Spec 1 → Spec 2 Handoff (preview)

After Spec 1 merges, Spec 2 (Series Generation Context) brainstorming begins. Spec 2 will consume:
- `KBRepository.find_merged_for_novel(novel_id)` — Canon + Overlay merge (Slice 1+2 Task 2.2)
- All Series CRUD endpoints (Slice 3)
- `Novel.series_id` + `series_position` (Slice 1 Task 1.3)

See `docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md` §„Notes for Spec 2" for preliminary open questions.

---

## Execution Handoff

**Plan complete and saved across 4 files in `docs/superpowers/plans/`.**

**Two execution options:**

### 1. Subagent-Driven (recommended)

I dispatch a fresh subagent per task, review between tasks, fast iteration. Each slice becomes a sequence of subagent invocations with review gates between.

- **REQUIRED SUB-SKILL:** superpowers:subagent-driven-development
- **Best for:** this plan — large, multi-slice, benefits from per-task review

### 2. Inline Execution

Execute tasks in this session using executing-plans, batch execution with checkpoints.

- **REQUIRED SUB-SKILL:** superpowers:executing-plans
- **Best for:** smaller plans or when context window allows

**Which approach?**

---

## Reference Quick-Links

- **Spec:** `docs/superpowers/specs/2026-07-29-series-foundation-design.md`
- **Cross-spec notes:** `docs/superpowers/specs/2026-07-28-series-cross-spec-notes.md`
- **Predecessor ADR:** `docs/architecture/decisions/ADR-074-author-voice-storage.md`
- **Successor ADR (to be written):** `docs/architecture/decisions/ADR-075-series-foundation.md`
- **Feature spec (to be written):** `docs/features/series/SERIES-001-foundation.md`
- **Visual mockups:** `_scratch/series-mockups/index.html` (gitignored; local artifacts)
