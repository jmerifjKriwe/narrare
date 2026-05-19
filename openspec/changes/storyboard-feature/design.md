## Context

Narrare stores a `story_structure` enum on the Novel model (`apps/api/narrare/novels/models.py`), selected during the setup wizard (Step 3) and editable via Settings → Novel Details. Five structures exist: `three_act`, `five_act`, `heros_journey`, `save_the_cat`, `seven_point`. Currently this value is used only as a prompt variable (`{{story_structure}}` in generation prompts) — it has no visual representation or structural influence on the writing experience.

The editor view (`packages/web/components/studio/EditorView.tsx`) is a full-height layout: toolbar → editor area with optional side panels (GenerationPanel, SessionPanel, MetadataSidebar). There is no structural overview of the story's architecture.

Three related planning features are specified (PLAN-003 Structure, PLAN-004 Timeline, PLAN-005 Storyboard) but none are implemented. They share significant overlap: all need chapter-to-structure mapping, visual chapter representation, and structural metadata.

**Key constraint**: This change introduces no LLM-based sync checking in the initial implementation. Sync status is computed from structural metadata only (stage assignment, planned beats vs outline existence). LLM-powered plan-vs-actual content comparison is a future enhancement.

## Goals / Non-Goals

**Goals:**
- Provide a visual, structure-aware storyboard that makes the novel's architecture visible at a glance
- Enable plan-vs-actual tracking at the structural level (is chapter in the right stage? does it have planned beats?)
- Support all 5 existing story structures with structure-specific stage layouts
- Allow story structure changes mid-project with position-based remap (AI-powered remap is future work)
- Enable drag & drop of chapter cards between stages for manual reorganization
- Establish the data model and adapter pattern that future planning features (timeline, full sync checking) can build on
- Integrate as a full-width collapsible panel above the entire editor area (including toolbar)
- Update feature documentation (PLAN-003, PLAN-004, PLAN-005) to reflect merged implementation

**Non-Goals:**
- LLM-powered semantic comparison of planned vs written content (future: sync checking with LLM)
- AI-powered chapter summarization for intelligent remapping (future: needs new LLM intent + prompt, `chapters.summary` column already exists)
- Full timeline management with date/time tracking (PLAN-004 — separate change)
- Auto-detection of story structure from written chapters (future: ANAL-011 integration)
- Adding new story structure types beyond the existing 5 (architecture supports it, but no new enum values in this change)
- Ripple analysis with impact severity scoring (future: depends on chapter dependency graph from KB relationships)

## Decisions

### D1: Structure Adapter Registry (Core)

**Decision**: Use a registry pattern in `packages/core/narrare_core/planning/` where each story structure has a pure-data adapter that defines its stages, beat expectations, and visual metadata.

**Rationale**: The 5 structures have fundamentally different stage counts (3 to 15), naming conventions, and beat patterns. A registry with adapters avoids a monolithic switch statement and makes future structure additions a single-file change.

**Structure**:
```
packages/core/narrare_core/planning/
├── __init__.py
├── adapters/
│   ├── __init__.py          # Registry: get_adapter(structure) -> StructureAdapter
│   ├── base.py              # StructureAdapter protocol, StageDef, BeatDef dataclasses
│   ├── three_act.py         # 3 stages, classic beats
│   ├── five_act.py          # 5 stages
│   ├── heros_journey.py     # 12 stages (Condensed to 8 visual cards)
│   ├── save_the_cat.py      # 15 beats across 3 acts
│   └── seven_point.py       # 7 turning points
├── models.py                # ChapterOutline, SyncStatus, StageAssignment dataclasses
└── sync.py                  # StructuralSyncChecker (no LLM, metadata-based)
```

**Adapter protocol**:
```python
class StructureAdapter(Protocol):
    structure_type: StoryStructure
    stages: list[StageDef]

    def suggest_stage(self, chapter_number: int, total_chapters: int) -> str: ...
    def validate_assignment(self, stage_id: str, chapter_number: int) -> bool: ...
    def get_beat_expectations(self, stage_id: str) -> list[BeatDef]: ...
```

**Alternatives considered**:
- YAML/JSON configuration files → Rejected: stages have logic (suggest_stage), not just data
- Single class with switch statements → Rejected: violates OCP, harder to test individually

### D2: Chapter Outlines Table (Backend)

**Decision**: New `chapter_outlines` table linked to `chapters` and `chapter_versions`, storing planned beats and stage assignments as JSONB.

**Schema**:
```sql
CREATE TABLE chapter_outlines (
    id UUID PRIMARY KEY,
    chapter_id UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    version_id UUID REFERENCES chapter_versions(id) ON DELETE SET NULL,
    stage_assignment VARCHAR(50) NOT NULL,  -- e.g., "act_1", "ordinary_world"
    planned_beats JSONB DEFAULT '[]',       -- [{title, description, completed}]
    outline_notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chapter_id)                      -- One outline per chapter
);
```

**Rationale**: JSONB for `planned_beats` allows structure-specific beat schemas without additional tables. The `version_id` link enables tracking outline changes across chapter versions. The UNIQUE constraint on `chapter_id` ensures one outline per chapter.

**Alternatives considered**:
- Store outlines in chapter frontmatter → Rejected: makes querying and API access harder
- Separate `planned_beats` table with normalized rows → Rejected: over-engineering for this stage, different structures have different beat schemas

### D3: Sync Status Calculation (Core)

**Decision**: Structural sync only — no LLM. Three status levels computed from metadata.

**Sync logic** (`sync.py`):
```python
class SyncStatus(StrEnum):
    EMPTY = "empty"           # No outline exists, no content written
    PLANNED = "planned"       # Outline exists, not yet written
    ON_TRACK = "on_track"     # Outline exists, content written, stage matches
    DEVIATED = "deviated"     # Content written but stage doesn't match outline
    COMPLETED = "completed"   # All planned beats marked completed
```

**Calculation**:
1. No outline + no content → `EMPTY`
2. Has outline + no content → `PLANNED`
3. Has outline + has content + stage matches → check beat completion → `ON_TRACK` or `COMPLETED`
4. Stage mismatch → `DEVIATED`

**Rationale**: This is fast, deterministic, and requires no LLM calls. Future LLM-based content analysis can add additional status types (`SEMANTIC_DEVIATION`) without changing this base.

### D4: Frontend Integration — Full-Width Storyboard Above Editor

**Decision**: Place the collapsible `StoryboardPanel` **above the toolbar and the entire editor area**, giving it full viewport width. Chapter cards are draggable between stages using @dnd-kit (already used in ChapterSidebar). When the storyboard exceeds viewport width, horizontal scroll with left/right arrow navigation is provided.

**Layout** (collapsed):
```
┌─────────────────────────────────────────────────────────────┐
│ ▶ Storyboard: 3-Act Structure — 12 chapters                 │ ← Full width
├─────────────────────────────────────────────────────────────┤
│ [Toolbar: B I | H2 H3 | ✨ Names | 🪄 Generate]             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              [Editor Area]                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Layout** (expanded):
```
┌─────────────────────────────────────────────────────────────┐
│ ▼ Storyboard: 3-Act Structure                         [⬅ ➡] │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ACT 1: Setup   │ ACT 2: Confrontation  │ ACT 3: Resol. │ │
│ │ [Ch1🟢][Ch2🟢] │ [Ch4🟢][Ch5🟢][Ch6🟡] │ [Ch7⬜][Ch8⬜]  │ │
│ │ [Ch3🟡]        │ [⬜drop zone]          │ [⬜]            │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ [Toolbar: B I | H2 H3 | ✨ Names | 🪄 Generate]             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              [Editor Area]                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key behaviors:**
- **Collapsed**: single summary row showing structure name, chapter count, toggle button
- **Expanded**: full stage layout with chapter cards, drag & drop enabled
- **Drag & Drop**: cards can be dragged between stages to reassign chapters. Drop zones shown on hover. Uses @dnd-kit's `DndContext`, `SortableContext`, `useDraggable`, `useDroppable` — same library as ChapterSidebar.
- **Horizontal scroll**: when stages + cards exceed viewport width, show ◀/▶ arrow buttons at the storyboard edges. Arrows appear only when overflow detected.
- **Click → navigate**: clicking a chapter card (without dragging) sets it as the active chapter in the editor, analogous to clicking in the sidebar chapter list.
- **Full width**: the storyboard sits above the sidebar/toolbar/editor columns, spanning the entire viewport width. This gives maximum horizontal space for stages and cards.

**Component structure**:
```
packages/web/components/studio/planning/
├── StoryboardPanel.tsx        # Full-width collapsible container with DndContext
├── StoryboardStageColumn.tsx  # Vertical stage column (droppable zone)
├── StoryboardCard.tsx         # Draggable chapter card (click → navigate)
├── SyncStatusBadge.tsx        # Color-coded status indicator
├── OutlineEditor.tsx          # Beat editor for selected chapter
├── StoryboardScrollArrows.tsx # Left/right scroll arrows for overflow
└── StructureChangeDialog.tsx  # Confirmation flow for structure changes
```

**Alternatives considered**:
- Between toolbar and editor → Rejected: limits storyboard to editor column width, doesn't leverage full viewport
- Side panel (like MetadataSidebar) → Rejected: structural overview needs horizontal space, not vertical
- Separate page (like Analysis) → Rejected: storyboard should be visible while writing, not a separate context switch
- Modal/overlay → Rejected: obscures the editor, defeats the "at a glance" purpose

### D4b: Drag & Drop with @dnd-kit

**Decision**: Use @dnd-kit (already a project dependency via ChapterSidebar drag-and-drop) for chapter card reordering and stage reassignment.

**Flow**:
1. User grabs a chapter card (drag handle or entire card)
2. Other stages show drop zones (highlighted borders)
3. User drops card on a stage → stage_assignment updated
4. Backend `PUT /api/v1/planning/outlines/{chapter_id}` with new `stage_assignment`
5. Storyboard re-fetches to reflect new layout
6. Chapter position (integer) remains unchanged — only stage assignment moves

**Rationale**: @dnd-kit is already integrated and tested in the project. Reusing it avoids adding a new dependency. The drag behavior mirrors the sidebar chapter reordering pattern users already know.

### D4c: Horizontal Scroll with Arrow Navigation

**Decision**: When the storyboard content exceeds viewport width, render ◀/▶ navigation arrows at the edges. Arrows are semi-transparent and overlay the storyboard edges.

**Implementation**:
- Use `useRef` on the scroll container to detect overflow via `scrollWidth > clientWidth`
- Arrow buttons positioned absolutely at left/right edges of the storyboard
- Click arrow → `scrollBy({ left: 200, behavior: 'smooth' })`
- Hide arrow when scrolled to start (◀) or end (▶)
- Touch/swipe also works natively via `overflow-x: auto`

**Rationale**: Arrows are discoverable, keyboard-accessible, and work well alongside the native scroll behavior. Pure CSS `overflow-x: auto` handles touch and trackpad scrolling.

### D5: Story Structure Change Workflow

**Decision**: When `story_structure` changes on a novel, the backend performs a best-effort remap of existing chapter outlines to the new structure's stages, then returns a preview for user confirmation.

**Flow**:
1. User changes structure in Settings → Novel Details → Save
2. `PUT /api/v1/novels/{id}` with new `story_structure`
3. Backend calls `remap_storyboard(novel_id, old_structure, new_structure)`
4. For each chapter with an outline:
   - Calculate position ratio: `chapter_number / total_chapters`
   - Map to new structure stage: `new_adapter.suggest_stage(chapter_number, total_chapters)`
   - Clear stage-specific beats (structure-specific), keep generic outline notes
5. Return remap preview in response: `{ remapped: [{chapter_id, old_stage, new_stage}] }`
6. Frontend shows `StructureChangeDialog` with preview
7. User confirms → outlines updated. User cancels → structure change reverted.

**Rationale**: Auto-remap based on position ratio works well for similar structures (three_act → five_act). For very different structures (three_act → heros_journey), the mapping may be imperfect, but the preview lets users adjust before committing.

**Alternatives considered**:
- Require manual reassignment → Rejected: too much friction for structure changes
- No remap, just clear all stage assignments → Rejected: loses existing planning data

### D6: API Design

**Decision**: New `/api/v1/planning/` endpoints following the existing domain module pattern.

**Endpoints**:
```
GET    /api/v1/planning/storyboard/{novel_id}          # Full storyboard view
GET    /api/v1/planning/storyboard/{novel_id}/sync      # Sync status for all chapters
GET    /api/v1/planning/outlines/{chapter_id}           # Get chapter outline
PUT    /api/v1/planning/outlines/{chapter_id}           # Update outline (beats, notes, stage)
POST   /api/v1/planning/storyboard/{novel_id}/remap     # Preview structure change remap
```

**Rationale**: The `/planning/` domain module follows the same contract-first pattern as all other modules (contracts.py → schemas.py → service.py → router.py). Storyboard and outlines are separate concerns but share the same domain.

## Risks / Trade-offs

**[Adapter complexity for save_the_cat]** → Mitigation: Save the Cat has 15 beats which is the most complex. Map beats to 3 visual act-groups in the UI, showing beats as nested items within act cards.

**[Stage assignment ambiguity for short novels]** → Mitigation: For novels with fewer chapters than structure stages, `suggest_stage()` collapses multiple stages. A 3-chapter novel in hero's journey (12 stages) maps chapters to beginning/middle/end groupings.

**[JSONB query performance for planned_beats]** → Mitigation: planned_beats are always loaded per-chapter (never filtered/sorted at DB level). No index needed.

**[EditorView.tsx is already 521 lines]** → Mitigation: StoryboardPanel is a self-contained component imported and toggled. EditorView gains ~15 lines (import + toggle button + conditional render), not the panel's full implementation. Follows RULE-04 (modularize, don't minify).

**[Structure change rollback complexity]** → Mitigation: Run structure change and outline remap in a single DB transaction. If remap fails, entire change rolls back.

**[No LLM sync means limited deviated detection]** → Accepted trade-off for this change. Structural sync catches stage mismatches and missing outlines. Content-level deviation detection is explicitly out of scope and tracked as future work.

## Future Work (TODO — documented, not implemented)

### F1: AI-Powered Structure Remap (depends on WRITE-012)

**Problem**: The position-ratio heuristic (`chapter_number / total_chapters → suggest_stage()`) works for similar structures but produces poor results when structures differ significantly (e.g., three_act → heros_journey).

**Proposed solution**: Once [WRITE-012 Chapter Summary](docs/features/writing/WRITE-012-chapter-summary.md) is implemented, the remap function can analyze chapter summaries (stored in the existing `chapters.summary` column) to suggest stage assignments based on narrative content rather than position. A chapter with a climactic confrontation summary would map to the climax stage regardless of its position.

**Dependency**: WRITE-012 is already fully specified — `SummaryService` with `LLMIntent.SUMMARIZE_CHAPTER`, auto-summarize on save, manual trigger endpoint. The storyboard only needs to consume the summaries, not build the summarization pipeline.

**Broader impact of WRITE-012**:
- [INFRA-003](docs/features/infra/INFRA-003-context-assembly.md) — Tier 2 (Recent History) currently loads full chapter content. With summaries, it could use condensed versions, dramatically reducing token usage.
- [CONS-001](docs/features/consistency/CONS-001-consistency-checker.md) — Cross-chapter context during checks.
- PLAN-005 Storyboard — Card summaries on hover, intelligent remap.

**Why not now**: WRITE-012 is a cross-cutting feature (LLM gateway, prompt system, event system) that deserves its own focused change. The storyboard works with position-based heuristics initially.
