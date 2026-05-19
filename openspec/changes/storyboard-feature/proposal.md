## Why

Stories evolve during writing — planned scenes get abandoned, directions change, new ideas emerge. Currently, Narrare stores a `story_structure` enum on the novel (chosen during setup wizard), but there is **no visual representation** of that structure and **no way to track** whether written chapters follow the planned outline. The three related planning features — Structure Visualization (PLAN-003), Timeline (PLAN-004), and Storyboard (PLAN-005) — are specified as separate features, but they share the same core concern: making the story's architecture visible and actionable. Building them as one cohesive "Planning" experience avoids fragmented UX and duplicated infrastructure.

## What Changes

- **New collapsible Storyboard Panel** positioned **above the toolbar and entire editor area** (full width), showing the story's structural overview (acts, stages, beats) mapped to actual chapters as **draggable cards** with color-coded sync status
- **Chapter Cards with Drag & Drop**: each chapter is a card within its assigned stage. Users can drag cards between stages to reassign chapters. Horizontal scrolling with arrow navigation when the storyboard exceeds viewport width.
- **Structure-aware layout engine** that adapts the storyboard to the novel's chosen story structure (three_act, five_act, heros_journey, save_the_cat, seven_point) — each structure defines its own visual stages and beat expectations
- **Plan-vs-Actual sync tracking**: chapters display sync status (synchronized, deviated, abandoned, impacted) based on comparison between planned outline and written content
- **Click-to-navigate**: clicking a chapter card in the storyboard activates that chapter in the editor (analogous to the chapter sidebar)
- **Story structure change workflow** (TODO — depends on AI chapter summarization): when the user changes the novel's story structure, AI-generated chapter summaries (stored in the existing `chapters.summary` column) enable intelligent remapping. For now, remap uses position-based heuristics. AI-powered remap is documented as a future enhancement.
- **Timeline integration point**: chapter metadata (timeline_position) feeds into the storyboard's chronological view — full timeline management (PLAN-004) remains a future enhancement
- **Additional story structures considered**: the architecture supports adding new structures via a registry pattern. Future additions (e.g., Kishōtenketsu, Dan Harmon's Story Circle, Freytag's Pyramid) require only a new adapter — no core changes.
- **Feature docs update**: after implementation, update PLAN-003, PLAN-004, PLAN-005 and related feature docs to reflect the merged implementation

## Capabilities

### New Capabilities
- `storyboard-engine`: Backend service for structure mapping, sync checking, ripple analysis, and chapter-to-stage assignment. Includes structure adapters for all 5 story structures.
- `storyboard-ui`: Full-width collapsible storyboard panel above the editor, structure-aware chapter cards with drag & drop, horizontal scroll with arrow navigation, sync status indicators, click-to-navigate to chapter, and structure change confirmation flow.
- `structure-adapters`: Registry-based adapter pattern mapping each StoryStructure enum value to its stages, beat expectations, and visual layout metadata. Each adapter is a pure data module (no LLM, no DB).
- `chapter-outline-storage`: Persistence layer for per-chapter planning data (planned beats, outline notes) stored alongside chapter versions. Enables plan-vs-actual comparison.

### Modified Capabilities
_(No existing spec-level requirement changes. The novel model's `story_structure` field already exists and is editable.)_

## Impact

**Backend (new `planning/` module):**
- New domain module: `apps/api/narrare/planning/` — follows contract-first pattern (contracts.py → schemas.py → service.py → router.py)
- New Alembic migration: `chapter_outlines` table linked to `chapters` and `chapter_versions`
- New API endpoints under `/api/v1/planning/` (storyboard view, sync check, outline CRUD, structure remap)

**Core (new `planning/` subpackage):**
- New: `packages/core/narrare_core/planning/` — structure adapters, sync logic (pure domain, no HTTP/DB)
- Structure adapter registry with 5 built-in adapters
- Sync comparison engine (semantic comparison of planned vs actual beats)

**Frontend (new `planning/` components):**
- New: `packages/web/components/studio/planning/` — StoryboardPanel (full-width, above toolbar), StoryboardCard (draggable), SyncStatusBadge, StructureChangeDialog
- EditorView.tsx modification: integrate collapsible storyboard panel above toolbar (full-width)
- Drag & Drop: using existing @dnd-kit library (already used in ChapterSidebar)
- i18n: new keys for storyboard UI, structure names, sync statuses (en, de, fr)

**Future work (documented as TODO, not implemented in this change):**
- AI Chapter Summarization: LLM-powered function to populate `chapters.summary` column (field already exists on model). Primary consumer: INFRA-003 Context Assembly (Tier 2 Recent History currently uses full chapter content — summaries would dramatically reduce token usage). Also needed for intelligent structure remapping. Depends on core/llm gateway + new LLM intent.
- AI-powered structure remap: use chapter summaries to suggest stage assignments when structure changes (replaces position-ratio heuristic)

**Data model:**
- New table: `chapter_outlines` (id, chapter_id, version_id, planned_beats JSONB, outline_notes, stage_assignment, created_at, updated_at)
- No changes to existing tables (novel.story_structure already exists)
