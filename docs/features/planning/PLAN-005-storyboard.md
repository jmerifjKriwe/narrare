---
id: PLAN-005
title: "Storyboard View"
status: in-progress
area: planning
mvp: false

ui_tooltip: "Compare planned outline against written chapters with ripple analysis."
ui_help_short: |
  See your story's structure at a glance. Storyboard organizes chapters into
  stages, tracks sync between plan and writing, and lets you reorganize by
  dragging — helping you keep your story on track.
ui_help_long: |
  ## Storyboard View

  See your story's shape. Storyboard organizes chapters into structural stages
  (acts, turning points) so you can see the big picture while writing.

  **Structure-Aware Layout:**

  Chapters are organized into columns based on your chosen story structure:
  - **Three-Act**: Setup → Confrontation → Resolution
  - **Five-Act**: Exposition → Rising Action → Climax → Falling Action → Resolution
  - **Hero's Journey**: 12 stages from Ordinary World to Return
  - **Save the Cat**: 15 beats across 3 acts
  - **Seven-Point**: 7 turning points for tight plotting

  **Sync Status:**

  Each chapter shows its sync status — how closely it follows the plan:
  - ⬜ **Empty**: No outline yet (gray)
  - 📘 **Planned**: Outline exists, chapter not started (blue)
  - 🟢 **On Track**: Chapter matches stage expectations (green)
  - 🟡 **Deviated**: Chapter drifted from planned stage (yellow)
  - 💎 **Completed**: Chapter finished and aligned (emerald)

  **How it works:**
  1. Open the storyboard panel (above the editor toolbar)
  2. See chapters organized into structure stages
  3. Drag chapters between stages to reorganize
  4. Click a chapter card to jump to it in the editor
  5. Edit chapter outlines with planned beats and notes
  6. Change story structure → see remap preview → confirm or cancel

  **Structure Change Workflow:**
  When you switch story structures (e.g., Three-Act → Hero's Journey):
  1. Preview how chapters remap to new stages
  2. Review the before/after for each chapter
  3. Confirm to apply, or cancel to revert

  **Best practices:**
  - Open storyboard while writing for spatial awareness
  - Keep outlines updated — sync status is only as good as your plans
  - Try different structures to find the best fit
  - Use drag & drop to experiment with chapter placement

  Available in the editor's storyboard panel.
ui_available_in: [planning, cli]

service: planning/service.py
contract: planning/contracts.py#StoryboardServiceProtocol
router: planning/router.py
prompt: ~
requires: [PLAN-003, WRITE-001]
---

# PLAN-005 — Storyboard View

## What it does

Organizes chapters into a structure-aware storyboard with stage columns (based
on story structure like Three-Act, Hero's Journey, etc.). Tracks sync between
planned outlines and written content using 5 status levels. Supports drag & drop
reorganization and structure change remap with preview.

## Why it exists

Writers lose spatial awareness while deep in a chapter. The storyboard provides
a bird's-eye view of the story's structure, showing which stage each chapter
occupies and whether it's on track. This makes structural problems visible
before they compound.

## How it works (User perspective)

1. Toggle storyboard panel open (above editor toolbar, full-width collapsible)
2. See chapters organized into structure stage columns
3. Each chapter card shows: title, word count, sync status badge
4. Drag chapters between stages to reassign
5. Click a chapter card to navigate to it in the editor
6. Expand a chapter to edit its outline (planned beats, notes)
7. Change story structure in settings:
   - Preview remap: see which chapters move to which stages
   - Confirm or cancel the structure change
8. Collapse storyboard to a summary row when focused on writing

## How it works (Technical)

**Entry point:** `GET /api/v1/planning/storyboard/{novel_id}`
**Service:** `StoryboardService` in `apps/api/narrare/planning/service.py`
**Contract:** `StoryboardServiceProtocol` in `apps/api/narrare/planning/contracts.py`
**Core adapters:** `StructureAdapterRegistry` in `packages/core/narrare_core/planning/adapters/`
**Sync checker:** `StructuralSyncChecker` in `packages/core/narrare_core/planning/sync.py`

**Storage:** `chapter_outlines` table (migration 0013), `ChapterOutline` SQLAlchemy model

**API endpoints** (under `/api/v1/planning/`):
- `GET /storyboard/{novel_id}` — Full storyboard view with stages and chapters
- `GET /sync/{novel_id}` — Sync status for all chapters
- `GET /outlines/{chapter_id}` — Get or auto-create chapter outline
- `PUT /outlines/{chapter_id}` — Update outline (beats, notes, stage)
- `POST /remap/{novel_id}` — Preview or confirm structure remap

**Sync status (5 levels, rule-based priority):**
```python
class SyncStatus(str, Enum):
    EMPTY = "empty"          # No outline exists, no content
    PLANNED = "planned"      # Outline exists, chapter not started
    DEVIATED = "deviated"    # Stage assignment differs from suggested
    COMPLETED = "completed"  # Summary + content exists (strong signal), OR all beats addressed
    ON_TRACK = "on_track"    # Aligned but still in progress
```

**Rule priority** (first match wins in `StructuralSyncChecker.calculate_sync_status`):
1. No stage AND no content → `EMPTY`
2. Has outline but no content → `PLANNED`
3. Stage mismatch → `DEVIATED`
4. **Has summary AND has content** → `COMPLETED` *(new: summary presence is a stronger signal than word count alone)*
5. All required beats addressed + word_count > 0 → `COMPLETED` *(fallback for chapters without summaries)*
6. Everything aligned → `ON_TRACK`

**Storyboard assembly:**
1. Fetch novel → get `story_structure` → resolve adapter from registry
2. Fetch chapters (ordered by position) → fetch/create outlines for each
3. Group chapters into stages based on `stage_assignment`
4. Calculate sync status per chapter using `StructuralSyncChecker`

**Drag & drop reorganization:**
- Frontend uses `@dnd-kit` (`useDraggable` on cards, `useDroppable` on columns)
- Click vs drag distinguished by movement threshold
- On drop: calls `PUT /outlines/{chapter_id}` with new `stage_assignment`
- Invalidates storyboard query to refresh

**Structure change workflow:**
1. User changes `story_structure` in settings
2. Frontend calls `POST /remap/{novel_id}` with `confirm=false` for preview
3. Backend calculates new stage for each chapter via `adapter.suggest_stage()`
4. Frontend shows `StructureChangeDialog` with before/after table
5. On confirm: backend updates all outlines + novel's `story_structure`
6. On cancel: frontend reverts local state, no API call

**Remap heuristic:**
Two modes, selected automatically based on summary coverage:

1. **Position-ratio** (fallback): Maps `chapter_position / total_chapters` to stage ranges. Each adapter defines stage boundaries as fractions of total story length. Used when <50% of chapters have summaries.

2. **AI-powered** (when summaries available): Uses `AIRemapService` in `packages/core/narrare_core/planning/remap.py` to analyze chapter summaries for narrative content. Activated when ≥50% of chapters have non-empty summaries (configurable threshold, default 0.5). Falls back to position-ratio for individual chapters whose summaries are insufficient.

**AI remap confidence:**
`AIRemapService.calculate_confidence()` returns a score based on summary coverage:
- `0.0` — No summaries available (uses position-ratio)
- `0.5` — Partial coverage (≥50% but <100% chapters have summaries)
- `1.0` — Full coverage (every chapter has a summary)

**Dependency:** AI remap requires [WRITE-012 Chapter Summary](../writing/WRITE-012-chapter-summary.md) to populate `chapters.summary`. The storyboard's `should_use_ai_remap()` helper checks coverage before activating AI mode.

Also benefits INFRA-003 Context Assembly (Tier 2 Recent History uses summaries instead of full chapter content).

**Frontend components** (7, all in `packages/web/components/studio/planning/`):
- `StoryboardPanel` — Full-width collapsible container, DndContext, stage layout
- `StoryboardCard` — Draggable chapter card with status badge
- `StoryboardStageColumn` — Droppable stage column
- `SyncStatusBadge` — Color-coded status indicator
- `StoryboardScrollArrows` — Horizontal scroll controls
- `OutlineEditor` — Inline beat checklist + notes editor
- `StructureChangeDialog` — Remap preview modal

**API client:** `packages/web/lib/api/planning.ts`
**Hooks:** `useStoryboard`, `useChapterOutline`, `useRemap` (TanStack Query)

## Constraints & Edge Cases

- Requires chapters to exist for storyboard to populate
- Sync status is rule-based: summary presence + content is the strongest COMPLETED signal; falls back to word-count heuristic when no summary exists
- Drag & drop stage reassignment updates outline only (not chapter content)
- Structure remap overwrites all stage assignments (no partial remap)
- No undo for confirmed remap (would need separate audit trail)
- AI remap requires ≥50% chapters with summaries (configurable); falls back to position-ratio when below threshold
- AI remap uses summary text analysis — accuracy depends on summary quality and structure adapter specificity
- Empty novels show empty stage columns with drop zone indicators
- Adapter registry validates structure type on access (raises for unknown types)

## Related Features

- [PLAN-003](PLAN-003-structure.md) — Structure adapters (core layer, used by storyboard for stage layout)
- [PLAN-004](PLAN-004-timeline.md) — Timeline integration (`timeline_position` field for chronological context)
- [WRITE-001](../writing/WRITE-001-editor.md) — Editor where storyboard panel lives
- [WRITE-012](../writing/WRITE-012-chapter-summary.md) — Provides chapter summaries consumed by enhanced sync status + AI-powered structure remap
- [INFRA-003](../infra/INFRA-003-context-assembly.md) — Consumes chapter summaries for Tier 2 Recent History (context assembly)

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-20` — Fully implemented: core structure adapters (5 types), backend service with 6 methods and 5 REST endpoints, frontend with 7 components + drag & drop + structure change workflow + i18n (3 locales). Status → in-progress.
- `2026-05-21` — AI-powered remap implemented (AIRemapService with chapter summary analysis, configurable 50% coverage threshold). Enhanced sync COMPLETED detection uses summary presence. Integrated with WRITE-012 Chapter Summary. WritingGraphStatus component added to editor.
