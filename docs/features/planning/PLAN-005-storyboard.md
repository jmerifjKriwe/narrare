---
id: PLAN-005
title: "Storyboard View"
status: planned
area: planning
mvp: false

ui_tooltip: "Compare planned outline against written chapters with ripple analysis."
ui_help_short: |
  See how your written chapters match your plans. Storyboard compares outline
  to actual content, identifies deviations, and analyzes downstream effects of
  changes — helping you keep your story on track.
ui_help_long: |
  ## Storyboard View

  Compare your plans against what you've actually written. Storyboard tracks
  the relationship between intention and execution.

  **Sync Checking:**

  Compare finished chapters against plans:
  - **Synchronized**: Chapter matches plan
  - **Deviated**: Drifted from plan (how and why)
  - **Abandoned**: Major planned elements not executed
  - **Impacted**: Affected by earlier chapter changes

  **Ripple Analysis:**

  See downstream effects of changes:
  - Which chapters are affected by this change
  - What needs to be updated
  - Severity of impact (critical/minor)
  - Suggested fixes

  **How it works:**
  1. Open Planning panel
  2. Click "Storyboard"
  3. For each chapter, see:
     - Plan: What was intended
     - Actual: What was written
     - Status: Sync status (color-coded)
     - Deviations: What changed from plan
  4. Click any chapter to see:
     - Detailed plan vs actual comparison
     - Specific deviations listed
     - Ripple effects on later chapters
  5. For changes, see:
     - Affected chapters highlighted
     - Impact severity
     - Update suggestions
  6. Update plans or fix content as needed

  **Status colors:**
  - 🟢 Green: Synchronized (matches plan)
  - 🟡 Yellow: Deviated (intentional changes)
  - 🔴 Red: Abandoned (planned elements missing)
  - 🔵 Blue: Impacted (affected by earlier changes)

  **Best practices:**
  - Plan before writing (even brief outlines)
  - Run sync checks after each chapter
  - Use ripple analysis before major rewrites
  - Update plans when story evolves naturally

  **Use cases:**
  - Track project completion
  - Identify abandoned plot threads
  - See effects of structural changes
  - Guide revision priorities

  Storyboard helps you ship what you planned — or understand why you changed
  direction. Either way, you're making informed choices.

  Available in Planning panel or via CLI:
  `narrare storyboard --novel <id> --check sync`
ui_available_in: [planning, cli]

service: storyboard/service.py
contract: planning/contracts.py#StoryboardServiceProtocol
router: storyboard/router.py
prompt: ~
requires: [PLAN-001, WRITE-001]
---

# PLAN-005 — Storyboard View

## What it does

Compares planned outlines (scene plans, chapter outlines) against written
content. Tracks sync status (synchronized, deviated, abandoned, impacted) and
provides ripple analysis for downstream effects of changes.

## Why it exists

Stories evolve during writing. Planned scenes get abandoned, directions
change, or new ideas emerge. Writers lose track of what was planned vs what
was written. Storyboard makes intention vs. execution visible.

## How it works (User perspective)

1. Open Planning panel
2. Click "Storyboard"
3. For each chapter, see:
   - **Plan summary**: What was intended
   - **Status indicator**: Color-coded sync status
   - **Deviations**: What changed from plan
4. Click any chapter for details:
   - Side-by-side plan vs actual
   - Specific deviations listed
   - What was abandoned (if any)
5. For changes, see ripple effects:
   - Later chapters affected
   - Severity of impact
   - Suggested updates

Use to track project completion, identify orphaned plot threads, or understand
how changes propagate through your story.

## How it works (Technical)

**Entry point:** `storyboard/router.py` → `GET /api/v1/storyboard/{novel_id}`
**Service:** `StoryboardService.check_sync()` in `storyboard/service.py`
**Contract:** `StoryboardServiceProtocol` in `planning/contracts.py`

**Sync status:**
```python
class ChapterSyncStatus:
    chapter_id: UUID
    status: "synchronized" | "deviated" | "abandoned" | "impacted"
    plan_summary: str  # From scene plan or outline
    deviations: list[str]  # What changed
    abandoned_elements: list[str]  # Planned but not written
    impact_from: list[UUID]  # Chapters that changed this one
```

**Sync checking:**
- Compares chapter content against scene plan (PLAN-001)
- Extracts actual beats from written text
- Compares planned vs actual beats
- Flags deviations (added/removed/changed elements)
- Identifies abandoned plan elements

**Ripple analysis:**
- Uses chapter metadata only (fast, no content analysis)
- Tracks dependencies between chapters (cliffhangers, subplots)
- When chapter changes: identifies affected chapters
- Calculates impact severity based on dependency strength

**Dependencies:**
- Cliffhanger resolutions (Chapter N → Chapter N+1)
- Subplot threads (appear in multiple chapters)
- Character arcs (continued across chapters)
- Timeline continuity (Chapter N establishes X for Chapter N+1)

## Constraints & Edge Cases

- Requires scene plans or chapter outlines to exist
- Comparison approximate (semantic, not literal)
- Ripple analysis uses metadata only (may miss content dependencies)
- Abandoned elements may be intentional (writer discretion)
- Impact severity estimated (not always accurate)
- No automatic fixing — manual updates required

## Related Features

- [PLAN-001](PLAN-001-scene-planning.md) — Source of plans
- [WRITE-001](../writing/WRITE-001-editor.md) — Source of actual content
- [PLAN-003](PLAN-003-structure.md) — Reorganization affects storyboard
- [ASSIST-001](../ai_assist/ASSIST-001-plot-check.md) — Plot guidance

## Status & History

- `project-init` — Added to registry as planned feature
