---
id: PLAN-003
title: "Story Structure Visualization"
status: stable
area: planning
mvp: false

ui_tooltip: "Visualize your story's structure: acts, arcs, and chapter organization."
ui_help_short: |
  See your story's architecture. Structure Visualization displays acts, arcs,
  chapter organization, and dramatic structure — helping you understand
  and refine your story's shape.
ui_help_long: |
  ## Story Structure Visualization

  Visualize your story's architecture. See the shape of your narrative from
  bird's-eye view.

  **What gets visualized:**

  **Act Structure**
  - Classical divisions (2-act, 3-act, 5-act)
  - Act boundaries and turning points
  - Chapter distribution per act
  - Dramatic questions per act

  **Arc Visualization**
  - Character arcs across story
  - Emotional arcs (sentiment over time)
  - Plot arcs (goal pursuit)
  - Thematic arcs (idea development)

  **Chapter Organization**
  - Chapter lengths and word counts
  - POV character distribution
  - Location changes
  - Time passage between chapters

  **Dramatic Structure**
  - Inciting incidents
  - Climax and resolution points
  - Rising/falling action
  - Subplot intersections

  **How it works:**
  1. Open Planning panel
  2. Click "Structure View"
  3. Choose visualization:
     - **Act Structure**: Classical divisions
     - **Arc Map**: Character/thematic arcs
     - **Chapter Flow**: Sequential overview
     - **Dramatic Structure**: Key plot points
  4. Interactive visualization appears:
     - Drag to pan, scroll to zoom
     - Hover for details
     - Click chapters to open
     - Filter by POV, location, etc.
  5. Reorganize by dragging chapters
  6. Export visualization as image

  **Use cases:**
  - Plan story structure before writing
  - Identify structural problems
  - Reorganize chapters for better flow
  - Understand pacing and rhythm
  - Present structure to collaborators

  **Best practices:**
  - Use after outline complete, before drafting
  - Revisit during revision to check structure
  - Combine with Gap Analysis to find holes
  - Export before major reorganizations

  Structure is your story's skeleton. Make it strong, flexible, and purposeful.

  Available in Planning panel or via CLI:
  `narrare planning structure --novel <id> --view acts`
ui_available_in: [planning, cli]

service: planning/service.py
contract: planning/contracts.py#StoryboardServiceProtocol
router: planning/router.py
prompt: ~
requires: [KB-001]
---

# PLAN-003 — Story Structure Visualization

## What it does

Interactive visualization of story structure. Displays acts, arcs, chapter
organization, and dramatic structure. Enables chapter reorganization and
structural analysis through visual interface.

## Why it exists

Structure is invisible while writing. Writers lose sight of the big picture,
leading to unbalanced stories, missed arcs, or weak climaxes. Structure
visualization makes narrative architecture visible and manipulable.

## How it works (User perspective)

1. Open Planning panel
2. Click "Structure View"
3. Choose visualization type:
   - **Act Structure**: Classical divisions (3-act, 5-act)
   - **Arc Map**: Character/thematic arcs
   - **Chapter Flow**: Sequential overview
   - **Dramatic Structure**: Key plot points
4. Interactive visualization appears:
   - Chapters shown as cards/bars
   - Color-coded by POV, location, etc.
   - Drag chapters to reorganize
   - Hover for details (word count, summary, etc.)
   - Click to open chapter in Editor
5. Use filters to focus on specific elements
6. Export as PNG or SVG

Visualize to understand, reorganize to improve.

## How it works (Technical)

**Core layer:** `packages/core/narrare_core/planning/adapters/`
**Entry point:** `GET /api/v1/planning/storyboard/{novel_id}` (via PLAN-005 Storyboard)
**Service:** `StoryboardService` in `apps/api/narrare/planning/service.py`
**Contract:** `StoryboardServiceProtocol` in `apps/api/narrare/planning/contracts.py`

**Structure adapters** (registered in `StructureAdapterRegistry`):

| Adapter | Stages | File |
|---------|--------|------|
| Three-Act Structure | 3 (act-1, act-2, act-3) | `adapters/three_act.py` |
| Five-Act Structure | 5 (act-1 through act-5) | `adapters/five_act.py` |
| Hero's Journey | 12 stages condensed to visual layout | `adapters/heros_journey.py` |
| Save the Cat | 15 beats in 3 acts | `adapters/save_the_cat.py` |
| Seven-Point Structure | 7 turning points | `adapters/seven_point.py` |

Each adapter implements the `StructureAdapter` Protocol:
- `stages` — list of `StageDef` with id, name, description, position
- `suggest_stage(chapter_position, total_chapters)` — maps a chapter to a stage
- `get_beat_expectations(stage_id)` — expected beats for a stage

**Structure visualization** is now part of the storyboard panel (PLAN-005), not a
separate view. The storyboard renders chapters organized into structure stages
with color-coded columns. Switching structures triggers a remap preview that
reassigns chapters to new stages.

**Reorganization:**
- Drag chapters between stage columns (via @dnd-kit)
- Updates chapter outline's `stage_assignment` via API
- Structure change workflow with remap preview (PLAN-005)

## Constraints & Edge Cases

- Maximum 100 chapters for visualization performance
- Auto-detection requires 5+ chapters
- Arc detection requires character POV tagging
- Dramatic structure detection approximate (not prescriptive)
- Reorganization requires chapter metadata updates
- Export limited to PNG/SVG (not editable formats)

## Related Features

- [PLAN-001](PLAN-001-scene-planning.md) — Scene-level planning
- [PLAN-005](PLAN-005-storyboard.md) — Storyboard view (uses structure adapters for stage layout and remap)
- [ANAL-011](../analysis/ANAL-011-plot-analysis.md) — Arc detection
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Chapter metadata

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-20` — Core structure adapters implemented (5 adapters + registry in `core/planning/adapters/`). Merged with PLAN-005 storyboard — structure visualization is now part of the storyboard panel, not a separate view.
- **2026-05-26:** Status updated to stable. Feature fully implemented as part of merged storyboard feature.
