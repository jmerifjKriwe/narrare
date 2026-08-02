---
id: SERIES-001
title: "Series Foundation"
status: stable
area: series
mvp: false  # post-MVP (Phase 6)

ui_tooltip: "Group multiple novels into a series with a shared canon Knowledge Base."
ui_help_short: |
  Create a series to group novels sharing a canon world (magic system, foundational
  characters, world rules). Each novel keeps its own per-book state (character
  evolution, new characters introduced); canon entries are shared across all books.
ui_help_long: |
  Series Foundation introduces the Series (Reihe) as a first-class object in Narrare.
  A series groups multiple novels that share a canon Knowledge Base (magic system,
  world rules, canonical character bios, foundational artifacts).

  Each novel in a series has two KB layers:
  - **Series-Canon**: shared across all books. Stable facts live here.
  - **Novel-Overlay**: per-book state. Character evolution per band, new locations
    introduced in a specific book, etc.

  Generation (Spec 2) will automatically merge Canon + the latest Overlay when
  writing book N. For now, both layers are browsable and editable, and you can
  promote or demote an entry between them.

  **API Endpoints:**
  - `POST /api/v1/series` — Create series
  - `GET /api/v1/series` — List the user's series
  - `GET /api/v1/series/{id}` — Get series details
  - `PATCH /api/v1/series/{id}` — Update series
  - `DELETE /api/v1/series/{id}` — Delete series (novels become standalones)
  - `GET /api/v1/series/{id}/novels` — List novels in series
  - `POST /api/v1/series/{id}/novels` — Preview adding a novel (join preview)
  - `POST /api/v1/series/{id}/novels/{novel_id}/apply` — Apply the join
  - `DELETE /api/v1/series/{id}/novels/{novel_id}` — Remove novel from series
  - `PATCH /api/v1/series/{id}/novels/reorder` — Reorder novels
  - `GET /api/v1/series/{id}/kb` — List Series-Canon entries
  - `POST /api/v1/series/{id}/kb` — Create a Canon entry
  - `GET/PATCH/DELETE /api/v1/series/{id}/kb/{entry_id}` — Canon entry CRUD
  - `POST /api/v1/novels/{novel_id}/kb/{entry_id}/promote` — Overlay → Canon
  - `POST /api/v1/novels/{novel_id}/kb/{entry_id}/demote` — Canon → Overlay

  **UI Location:** Dashboard (mixed Series + Standalone cards) → `/series/[id]`
  workspace (4 tabs: Bände, Canon KB, Settings, Voice-placeholder).

ui_available_in: [dashboard, series-workspace]

service: series/service.py
contract: series/contracts.py#SeriesServiceProtocol
router: series/router.py
requires: [KB-001]  # KB extended with the scope concept; no other hard dependency
---

# SERIES-001 — Series Foundation

## What it does

Group multiple novels into a series with a shared canon Knowledge Base. Each
novel retains its own per-book state (Novel-Overlay); stable, series-wide facts
live in a shared layer (Series-Canon).

## Why it exists

Narrare had no series concept. Multi-book series were isolated projects with
duplicated worldbuilding — the magic system re-defined in every book, canonical
character bios drifting between bands. Series Foundation introduces a two-layer
KB model: **Series-Canon** (shared, stable facts) + **Novel-Overlay** (per-book
state), so each fact lives at the scope where it is actually stable.

This is the foundation spec (Spec 1 of 5) for the Series program. Later specs add
Series Generation Context (Spec 2), Series Voice Hierarchy (Spec 3), Cross-Novel
Drift (Spec 4), and Series Export (Spec 5).

## How it works (User perspective)

1. Create a series from the Dashboard ("+ New Series").
2. Add novels to the series via "Add Novel" in the Series-Workspace.
3. A **Preview** shows what would happen to each KB entry on join (which entries
   would become Canon, which stay Overlay).
4. Apply — entries are promoted to Canon or kept as Overlay based on entity type.
5. Browse the Series-Canon KB in the workspace's Canon tab.
6. Edit Canon entries there, or toggle an entry's scope from within any novel's
   KB editor (the **ScopeToggle**), with confirmation on both directions.

## How it works (Technical)

- **Data model:** `series` + `series_settings` tables; `novels.series_id` FK
  (nullable, `ON DELETE SET NULL` → novel becomes standalone if its series is
  deleted) + `series_position` + `subtitle`; `kb_entries` extended with
  `series_id`, `base_entry_id`, and `novel_id` made nullable. A single physical
  table with discriminated Pydantic types (STI).
- **Scope:** two layers — **Series-Canon** (`novel_id IS NULL`, shared) and
  **Novel-Overlay** (`novel_id IS NOT NULL`, per-book). Enforced physically by
  the `ck_kb_entries_scope_invariant` CHECK + two partial unique indexes
  (`uq_kb_canon_per_series`, `uq_kb_overlay_per_novel`), and logically by the
  Core STI types (`SeriesKBEntry`, `NovelKBEntry`).
- **Migration policy α (join):** when joining a series, if Canon is empty,
  Policy iii heuristics promote `system/concept/setting/location/object/timeline`
  entries to Canon; `character/faction` stay Overlay. If Canon is non-empty, all
  joining entries stay Overlay. The plan is shown in a Preview step before Apply.
- **Backward compatibility:** existing KB queries continue to work; Canon rows
  (`novel_id IS NULL`) are excluded from `WHERE novel_id = X` by design — a
  backward-compat regression test verifies this.

### Backend (implemented)

- `apps/api/narrare/series/` — full domain: `models`, `contracts`
  (`SeriesRepositoryProtocol` / `SeriesServiceProtocol` /
  `SeriesJoinServiceProtocol`), `schemas`, `repository`, `service` (CRUD + status
  transitions), `join_service` (Policy α preview/apply), `router`,
  `router_novels`, `dependencies`. Mirrors the `novels/` pattern.
- `apps/api/narrare/kb/scope_repository.py` — `KBScopeRepository`:
  `find_canon_for_series`, `find_overlay_for_novel`, `find_merged_for_novel`
  (Canon + latest-Overlay merge; Overlay wins on slug collision — pre-built for
  Spec 2), `promote_to_canon`, `demote_to_overlay`.
- `apps/api/narrare/kb/canon_service.py` — `KBCanonService` (Canon CRUD);
  `router_canon.py` (Canon CRUD endpoints); `router_scope.py` (promote/demote).
- `apps/api/alembic/versions/0037_series_foundation.py` — atomic `upgrade()` +
  `downgrade()` (RULE-14).

### Core (implemented)

- `packages/core/narrare_core/series/schemas.py` — `Series`, `SeriesSettings`
  Pydantic types (pure; no HTTP/DB).
- `packages/core/narrare_core/kb/schemas/entry.py` — STI hierarchy
  (`KBEntryBase` → `SeriesKBEntry`, `NovelKBEntry`; discriminated union
  `KBEntry`).

### Frontend (implemented)

- `/series/[id]` workspace with 4-tab routing (Bände / Canon KB / Settings /
  Voice-placeholder); mixed Series + Standalone cards on the Dashboard.
- `ScopeToggle` integrated into the KB editor (hidden when the novel is a
  standalone; confirmation-gated for both promote and demote).
- `CanonKBTab` + `CanonKBEditor` for the Canon tab.
- TanStack Query hooks: `useSeries` / `useSeriesList` / `useSeriesJoin`,
  `useCanonKB`, `useKBScope` (promote/demote), `useNovelSeries`.
- i18n across `dashboard.series.*`, `series.workspace.*`, `series.bände.*`,
  `series.canon.*`, `series.settings.*`, `series.join.*`, `kb.scope.*`
  (en/de/fr parity).

## Constraints & Edge Cases

- A novel belongs to at most one series (Single-Series in Spec 1; Crossover is
  deliberately YAGNI — the migration path to a join-table is known but not
  pre-built).
- Deleting a series: member novels become standalones (`novels.series_id` →
  NULL via `ON DELETE SET NULL`); `SeriesSettings` is CASCADE-deleted. **Canon
  KB rows are deleted in-transaction by `delete_series`** (the Canon fate — a
  Canon entry has no novel to fall back to, so it cannot survive its series);
  member novels' **Novel-Overlay KB rows survive** as standalone-novel entries
  (`kb_entries.series_id` is `ON DELETE SET NULL`, mirroring `novels.series_id`
  — see ADR-075 §D6). *(CR-04 correction, PR #145: the original CASCADE on
  `kb_entries.series_id` destroyed overlays of member novels on series delete.)*
- Promote requires confirmation (the entry becomes visible to all books).
- Demote requires confirmation (the entry leaves canon; other books lose it). A
  **409 ConflictError is returned if demoting would remove the Canon entry from
  the merged view of any OTHER member novel that relies on it as Canon** (i.e.
  any member novel that does not itself carry a same-slug Overlay). This is the
  Canon-integrity guard — demoting a Canon entry depended on by other books is
  blocked rather than silently orphaning their references (RULE-11). *(CR-04
  correction, PR #145: this guarantee was documented but not implemented.)*
- Status transitions: `draft → active → completed` (and back). No skipping.
- A standalone novel sees no ScopeToggle (graceful, not an error).

## Related Features

- KB-001 (Entity Management) — KB extended with the scope concept.
- WRITE-011 (Volume Management) — Volume is intra-novel chapter grouping; Series
  is inter-novel grouping. Volume ≠ Series.
- ADR-074 (Author Voice Storage) — Review Trigger partially closed (Series-
  storage-Teil); Voice-Teil remains open for Spec 3.
- ADR-075 (Series Foundation) — full architectural decision.

## Status & History

- **2026-07-29:** Feature spec created as part of Series Foundation Spec 1
  (Foundation + KB Evolution); implemented across all layers. Commit range
  `46a5c425`→`37f0cc17`.
