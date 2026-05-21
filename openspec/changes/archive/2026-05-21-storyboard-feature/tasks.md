## 1. Core: Structure Adapters (pure data, no dependencies)

- [x] 1.1 Create `packages/core/narrare_core/planning/__init__.py` and `planning/adapters/__init__.py` with empty exports
- [x] 1.2 Implement `planning/adapters/base.py` — `StructureAdapter` Protocol, `StageDef` dataclass, `BeatDef` dataclass, `StructureAdapterRegistry` class
- [x] 1.3 Implement `planning/adapters/three_act.py` — 3 stages (act-1, act-2, act-3) with beat expectations per stage
- [x] 1.4 Implement `planning/adapters/five_act.py` — 5 stages with beat expectations
- [x] 1.5 Implement `planning/adapters/heros_journey.py` — 12 stages condensed to visual layout with beat expectations
- [x] 1.6 Implement `planning/adapters/save_the_cat.py` — 15 beats organized in 3 acts
- [x] 1.7 Implement `planning/adapters/seven_point.py` — 7 turning points with beat expectations
- [x] 1.8 Write unit tests for all 5 adapters — verify stages, suggest_stage(), get_beat_expectations(), unknown inputs

## 2. Core: Sync Checker & Models

- [x] 2.1 Create `planning/models.py` — `ChapterOutlineData`, `SyncStatus` enum, `StageAssignment` dataclass, `StoryboardView` dataclass
- [x] 2.2 Implement `planning/sync.py` — `StructuralSyncChecker` with 5 status levels (empty, planned, on_track, deviated, completed)
- [x] 2.3 Write unit tests for `StructuralSyncChecker` — test all 5 status calculation scenarios with edge cases

## 3. Backend: Chapter Outline Storage

- [x] 3.1 Create Alembic migration for `chapter_outlines` table (id, chapter_id FK, version_id FK nullable, stage_assignment VARCHAR(50), planned_beats JSONB, outline_notes TEXT, timestamps, UNIQUE chapter_id)
- [x] 3.2 Implement `apps/api/narrare/planning/models.py` — `ChapterOutline` SQLAlchemy model matching migration schema
- [x] 3.3 Implement `apps/api/narrare/planning/contracts.py` — `OutlineRepositoryProtocol`, `StoryboardServiceProtocol` with method signatures
- [x] 3.4 Implement `apps/api/narrare/planning/schemas.py` — Pydantic request/response schemas for outlines and storyboard (BeatSchema, OutlineRequest, OutlineResponse, StoryboardStageResponse, StoryboardResponse, SyncStatusResponse, RemapPreviewItem, RemapRequest, RemapResponse)
- [x] 3.5 Implement `apps/api/narrare/planning/repository.py` — `OutlineRepository` with get_by_chapter_id, create, update, get_all_for_novel methods
- [x] 3.6 Register planning models in Alembic `env.py` auto-import

## 4. Backend: Planning Service & Router

- [x] 4.1 Implement `apps/api/narrare/planning/service.py` — `StoryboardService` with get_storyboard, get_sync_status, get_or_create_outline, update_outline, preview_remap, confirm_remap methods
- [x] 4.2 Implement `apps/api/narrare/planning/router.py` — REST endpoints: GET storyboard, GET sync, GET outline, PUT outline, POST remap
- [x] 4.3 Add planning router to `apps/api/narrare/_app/main.py` with `/api/v1/planning` prefix
- [x] 4.4 Write unit tests for `StoryboardService` — storyboard view assembly, outline CRUD, remap preview calculation, auto-create outlines on first access
- [x] 4.5 Write integration tests for planning API endpoints — full CRUD cycle, remap flow, error cases (404, validation)

## 5. Frontend: Planning Components

- [x] 5.1 Create `packages/web/components/studio/planning/SyncStatusBadge.tsx` — color-coded badge component (empty=gray, planned=blue, on_track=green, deviated=yellow, completed=emerald)
- [x] 5.2 Create `packages/web/components/studio/planning/StoryboardCard.tsx` — draggable chapter card (via @dnd-kit useDraggable) with title, status badge, word count; click handler to set active chapter (distinguishes click from drag via threshold)
- [x] 5.3 Create `packages/web/components/studio/planning/StoryboardStageColumn.tsx` — vertical stage column with droppable zone (via @dnd-kit useDroppable), header with stage name, chapter cards, empty drop zone indicator
- [x] 5.4 Create `packages/web/components/studio/planning/StoryboardScrollArrows.tsx` — left/right scroll arrow buttons; detects overflow via ref on parent; hidden at scroll boundaries
- [x] 5.5 Create `packages/web/components/studio/planning/StoryboardPanel.tsx` — full-width collapsible container positioned above toolbar; DndContext wrapping all stage columns; collapsed summary row; expanded stage layout with horizontal scroll + arrows; structure-aware rendering
- [x] 5.6 Create `packages/web/components/studio/planning/OutlineEditor.tsx` — inline editor with beat checklist (toggle completed), editable outline notes textarea, auto-save on change
- [x] 5.7 Create `packages/web/components/studio/planning/StructureChangeDialog.tsx` — modal dialog showing remap preview table, confirm/cancel buttons, loading state during remap
- [x] 5.8 Add planning API client — `packages/web/lib/api/planning.ts` with getStoryboard, getSyncStatus, getOutline, updateOutline (with stage reassignment), previewRemap, confirmRemap functions
- [x] 5.9 Add planning hooks — `packages/web/lib/hooks/usePlanning.ts` with useStoryboard, useChapterOutline, useRemap hooks (TanStack Query)

## 6. Frontend: Editor Integration

- [x] 6.1 Add storyboard toggle state to `packages/web/lib/stores/editorStore.ts` — storyboardOpen boolean, toggleStoryboard action
- [x] 6.2 Integrate StoryboardPanel into `packages/web/components/studio/EditorView.tsx` — render StoryboardPanel above the toolbar (full-width), conditional on storyboardOpen
- [x] 6.3 Wire StoryboardCard click → editorStore.setActiveChapterId for chapter navigation (same behavior as sidebar chapter list)
- [x] 6.4 Wire drag-and-drop stage reassignment → call updateOutline API with new stage_assignment → invalidate storyboard query
- [x] 6.5 Add StoryboardPanel keyboard shortcut registration in CommandPalette commands.ts

## 7. Frontend: Structure Change Flow

- [x] 7.1 Modify `packages/web/components/studio/settings/NovelDetailsTab.tsx` — on story_structure save, check if structure changed; if changed, call remap preview API and show StructureChangeDialog
- [x] 7.2 Wire StructureChangeDialog confirm → call confirmRemap API → invalidate storyboard query → close dialog
- [x] 7.3 Wire StructureChangeDialog cancel → revert local story_structure state → close dialog

## 8. i18n

- [x] 8.1 Add storyboard i18n keys to `packages/i18n/messages/en/studio.json` — stage names for all 5 structures, sync status labels, button text, dialog text, outline editor labels, drag & drop hints
- [x] 8.2 Add corresponding keys to `packages/i18n/messages/de/studio.json`
- [x] 8.3 Add corresponding keys to `packages/i18n/messages/fr/studio.json`

## 9. Testing & Validation

- [x] 9.1 Write unit tests for StoryboardPanel, StoryboardCard, SyncStatusBadge, StoryboardScrollArrows components (Vitest + Testing Library)
- [x] 9.2 Write unit tests for drag-and-drop behavior — verify stage reassignment on drop, cancel returns card
- [x] 9.3 Write unit tests for StructureChangeDialog component
- [x] 9.4 Write unit tests for planning API client functions
- [x] 9.5 Run `scripts/check_architecture.py` — verify no file exceeds size limits, all RULE-XX constraints pass
- [x] 9.6 Run full test suite (backend + frontend) — no regressions

## 10. Feature Documentation Update

- [x] 10.1 Update `docs/features/planning/PLAN-003-structure.md` — reflect merged implementation (structure adapters, stage-aware layout, part of storyboard panel)
- [x] 10.2 Update `docs/features/planning/PLAN-004-timeline.md` — document timeline integration point in storyboard (timeline_position field usage), mark full timeline management as future
- [x] 10.3 Update `docs/features/planning/PLAN-005-storyboard.md` — comprehensive update: new technical details, sync status, drag & drop, structure change workflow, full-width panel design
- [x] 10.4 Update `docs/features/INDEX.md` — change PLAN-003/004/005 status from "planned" to "in-progress", add cross-references
- [x] 10.5 Update `docs/_shared/CURRENT_STATE.md` — add planning module to "What Exists", update Phase 5 progress
- [x] 10.6 Add TODO comment in code for AI-Powered Structure Remap (future work: depends on [WRITE-012 Chapter Summary](docs/features/writing/WRITE-012-chapter-summary.md) — once `chapters.summary` is populated by WRITE-012, remap can analyze summaries for intelligent stage suggestions instead of position-ratio heuristic)

## TODO (Future Work — not implemented in this change)

- **AI-Powered Structure Remap**: Replace position-ratio heuristic with summary-based stage suggestion. Depends on [WRITE-012 Chapter Summary](docs/features/writing/WRITE-012-chapter-summary.md) which is already specified (`SummaryService`, `LLMIntent.SUMMARIZE_CHAPTER`, auto-summarize on save). Once WRITE-012 populates `chapters.summary`, the storyboard remap can analyze summaries to suggest stage assignments based on narrative content. WRITE-012 also benefits INFRA-003 Context Assembly (Tier 2 Recent History → summaries instead of full content) and CONS-001 Consistency Checker.
