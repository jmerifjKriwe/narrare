## Context

Narrare has a volumes backend at `apps/api/narrare/volumes/` with basic CRUD (list, create, update, delete). The `chapters` table already has a nullable `volume_id` FK (`ondelete="SET NULL"`). A placeholder frontend exists at `packages/web/app/(studio)/novel/[id]/volumes/page.tsx` rendering `VolumeManagementPlaceholder.tsx`. The Sidebar component shows a "Volumes" nav item pointing to this placeholder. i18n keys exist in all 3 locales but contain only "coming soon" strings.

The current Volume model (`models.py`) has: `id`, `novel_id`, `title`, `position`, `created_at` — no subtitle, description, word-count target, or `is_default` flag.

## Goals / Non-Goals

**Goals:**
- Complete the backend: model enrichment (subtitle, description, word_count_target, is_default), default volume auto-creation on novel creation, volume statistics endpoint, volume reordering endpoint, chapter–volume assignment in chapter CRUD
- Build the frontend: volume management page replacing the placeholder, volume selector dropdown in the sidebar chapter list, chapter list filtered by active volume, volume statistics display in the MetadataSidebar

**Non-Goals:**
- Volume switching with state preservation (scroll position, cursor) — deferred to a follow-up change
- Context assembly integration (volume-scoped context for AI) — depends on context assembly being built first
- Cross-volume consistency checks (CONS-001) — separate feature
- Volume-scoped export (IO-001) — separate feature
- Drag-and-drop volume reordering in the UI (backend supports it, but UI DnD is deferred to avoid scope creep)

## Decisions

### D1: Default volume auto-creation via NovelService

**Decision**: After creating a novel, the `NovelService.create()` method will also create a default volume with `is_default=True`, titled "Volume 1" (or locale-appropriate default).

**Rationale**: The feature spec states "every novel starts with a single default volume" and "chapters are never orphaned". Creating the default volume at novel-creation time ensures no novel exists without a volume. Using `is_default` flag (rather than convention like `position=0`) makes the invariant explicit and queryable.

**Alternatives considered**:
- _Database trigger_: Would work but bypasses the service layer (violates RULE-06)
- _Lazy creation on first chapter_: Risky — what if user navigates to volumes page before creating a chapter?

### D2: Volume statistics computed on read (not stored)

**Decision**: The `GET /volumes/{id}/stats` endpoint computes word count, chapter count, and completion percentage on-the-fly via SQL aggregation.

**Rationale**: Volume statistics change on every chapter save. Storing them would require updating on every chapter mutation (create, update content, delete, reassign volume) — high write amplification for data that is read infrequently. At our scale (2–10 volumes, hundreds of chapters per novel), aggregation queries are sub-millisecond.

**Alternatives considered**:
- _Materialized statistics column_: Premature optimization, adds sync complexity
- _Cache in Redis_: Unnecessary at current scale, adds invalidation complexity

### D3: Active volume stored in frontend state only

**Decision**: The "active volume" is stored in `editorStore` (Zustand). The chapters query uses `volume_id` as a filter parameter. No server-side "active volume" concept.

**Rationale**: Volume switching is a UI concern — it determines which chapters appear in the sidebar. The backend does not need to track which volume a user is "in". The sidebar fetches chapters filtered by `?volume_id=X` or all chapters when no volume filter is active. This keeps the backend simple and avoids a "volume state" API.

**Alternatives considered**:
- _Server-side volume switch endpoint (POST /switch)_: Over-engineering; the spec mentions it but the actual need is just client-side filtering
- _URL-based volume state (`/novel/{id}?volume=X`)_: Would work but adds routing complexity for no benefit — the sidebar is the primary view

### D4: Volume selector as a dropdown in the Sidebar chapter section header

**Decision**: Replace the "Chapters" section header in `Sidebar.tsx` with a dropdown that shows the active volume name and allows switching. The chapter list below filters to the selected volume. An "All" option shows chapters across all volumes.

**Rationale**: The sidebar already has a chapter list. Adding a dropdown above it is the least-disruptive UI change. It avoids a separate "volume selector" component that would take additional screen space.

**Alternatives considered**:
- _Tabs (Volume 1 | Volume 2 | ...)_: Doesn't scale with 5+ volumes, takes horizontal space
- _Separate panel_: Too heavy for a switching action; the management page handles CRUD

### D5: Volume management page as full CRUD form

**Decision**: Replace `VolumeManagementPlaceholder` with a proper management page: list of volumes with inline editing, create/delete/reorder actions, and statistics per volume.

**Rationale**: The page already exists in the route structure and sidebar navigation. Using it for full CRUD keeps the sidebar lightweight (dropdown only) while providing a dedicated space for volume management.

### D6: Chapter–volume assignment via `volume_id` field

**Decision**: Add `volume_id` (optional UUID) to chapter create/update schemas. When creating a chapter from the sidebar, it auto-assigns the currently active volume. Chapters can be moved between volumes via the volume management page or chapter settings.

**Rationale**: The FK already exists in the `chapters` table. We just need to expose it in the API schemas and wire it through the service layer. Default assignment to the active volume reduces user friction.

## Risks / Trade-offs

**[Default volume deletion protection]** → The `is_default` flag prevents deletion of the default volume in the service layer. If a user somehow gets a novel with no default volume (data corruption), the system creates one on-the-fly when listing volumes. Risk is low since volume deletion goes through service validation.

**[Chapter reassignment on volume deletion]** → When a non-default volume is deleted, its chapters' `volume_id` is set to NULL (existing `ondelete="SET NULL"`). The sidebar's "All" view catches these orphaned chapters. The default volume auto-creation ensures there's always at least one volume to reassign to manually.

**[No DnD reordering UI yet]** → The backend supports position-based reordering (`PATCH /reorder`), but the initial UI will use simple up/down arrow buttons instead of full drag-and-drop. This reduces scope while keeping the backend future-ready.

**[i18n expansion]** → New translation keys needed for volume management UI (form labels, buttons, stats, error messages). Must be added in all 3 locales (en, de, fr). Using the existing `studio.json` namespace's `volumes` section.
