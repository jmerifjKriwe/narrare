---
id: PLAN-003
title: "Story Structure Visualization"
status: planned
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
contract: planning/contracts.py#StructureServiceProtocol
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

**Entry point:** `planning/router.py` → `GET /api/v1/planning/structure/{novel_id}`
**Service:** `StructureService.get_structure()` in `planning/service.py`
**Contract:** `StructureServiceProtocol` in `planning/contracts.py`

**Structure data:**
```python
class StoryStructure:
    acts: list[Act]  # User-defined or auto-detected
    chapters: list[ChapterSummary]
    arcs: list[ArcSummary]  # Character/thematic arcs
    plot_points: list[PlotPoint]  # Inciting incident, climax, etc.

class ChapterSummary:
    id: UUID
    number: int
    title: str
    word_count: int
    pov_character: str | None
    location: str | None
    act: int | None
```

**Visualization types:**
- **Act structure**: Hierarchical view of acts → chapters
- **Arc map**: Timeline view of character/thematic development
- **Chapter flow**: Sequential bar chart with metadata
- **Dramatic structure**: Key plot points on tension curve

**Reorganization:**
- Drag chapters to new positions
- Updates chapter.number automatically
- Frontmatter updated to match
- Reorg suggestions logged (undo available)

## Constraints & Edge Cases

- Maximum 100 chapters for visualization performance
- Auto-detection requires 5+ chapters
- Arc detection requires character POV tagging
- Dramatic structure detection approximate (not prescriptive)
- Reorganization requires chapter metadata updates
- Export limited to PNG/SVG (not editable formats)

## Related Features

- [PLAN-001](PLAN-001-scene-planning.md) — Scene-level planning
- [PLAN-005](PLAN-005-storyboard.md) — Plan vs tracking
- [ANAL-011](../analysis/ANAL-011-plot-analysis.md) — Arc detection
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Chapter metadata

## Status & History

- `project-init` — Added to registry as planned feature
