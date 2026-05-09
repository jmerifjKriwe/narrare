---
id: PLAN-001
title: "Scene Planning"
status: planned
area: planning
mvp: false

ui_tooltip: "Plan scenes with beats, goals, and conflicts before writing."
ui_help_short: |
  Plan each scene before writing. Define beats, goals, conflicts, and outcomes.
  Scene Planning helps you write with direction and ensures every scene has
  a purpose in your story.
ui_help_long: |
  ## Scene Planning

  Plan scenes with structure and purpose before you write. Every scene should
  move your story forward — Scene Planning ensures it does.

  **What to plan for each scene:**

  **Scene Basics**
  - Scene number and position in chapter
  - POV character
  - Location and setting
  - Timeframe

  **Scene Purpose**
  - What happens in this scene?
  - What's the goal?
  - How does it move the story forward?
  - What changes by the end?

  **Characters**
  - Who's present?
  - What do they want?
  - What's in their way?
  - What do they learn?

  **Beats (Scene Structure)**
  - Entry point (how scene begins)
  - Key events and actions
  - Dialogue exchanges
  - Turning point
  - Exit point (how scene ends)

  **Conflict**
  - What's at stake?
  - Who wants what?
  - What prevents them from getting it?
  - How does the scene resolve?

  **How it works:**
  1. Open chapter in Editor
  2. Click "Plan Scene" for any scene
  3. Planning panel appears with fields:
     - Scene basics (POV, location, etc.)
     - Purpose statement
     - Character goals and obstacles
     - Beat-by-beat outline
     - Conflict and resolution
  4. Fill in as much or little as you want
  5. Save plan
  6. Write the scene following your plan

  **Planning modes:**
  - **Detailed**: Full beat sheet with every action
  - **Simple**: Goal, conflict, resolution only
  - **Flexible**: Bullet points, no strict structure

  **Best practices:**
  - Plan before writing (not after)
  - Know your scene's purpose going in
  - Not every scene needs equal planning
  - Adjust plans as you discover better directions

  **Benefits:**
  - Write faster (direction already decided)
  - Avoid meandering scenes
  - Ensure every scene has purpose
  - Maintain consistency with outline

  Scene plans live alongside your writing. Update them as your story evolves.
  They're plans, not prisons — change them when needed.

  Available in Editor → Scene Planning panel or via CLI.
ui_available_in: [editor, cli]

service: planning/service.py
contract: planning/contracts.py#PlanningServiceProtocol
router: planning/router.py
prompt: core/prompts/_bundled/planning/en/scene
requires: [KB-001]
---

# PLAN-001 — Scene Planning

## What it does

Pre-writing scene planning tool. Define scene basics (POV, location), purpose
statement, character goals, beat-by-beat outline, and conflict/resolution.
Plans guide writing and ensure scenes serve story purpose.

## Why it exists

Pantsers write into dead ends. Planners over-structure and lose spontaneity.
Scene planning provides enough structure to write with purpose, enough flexibility
to discover magic along the way. Every scene should have a reason to exist.

## How it works (User perspective)

1. Open chapter in Editor
2. Click "Plan Scene" (or use keyboard shortcut)
3. Planning panel opens with fields:
   - **Scene**: Position in chapter, POV, location
   - **Purpose**: What happens, why it matters
   - **Characters**: Who's present, what they want
   - **Beats**: Key events in order
   - **Conflict**: What's at stake, how it resolves
4. Fill in as much/little as you want
5. Save plan
6. Plan appears in sidebar while writing
7. Update plan anytime as story evolves

Write following your plan, or change direction and update the plan. The plan
serves you, not the other way around.

## How it works (Technical)

**Entry point:** `planning/router.py` → `POST /api/v1/planning/scenes`
**Service:** `PlanningService.create_scene_plan()` in `planning/service.py`
**Contract:** `PlanningServiceProtocol` in `planning/contracts.py`

**Scene plan structure:**
```python
class ScenePlan:
    id: UUID
    chapter_id: UUID
    scene_number: int
    pov_character_id: UUID | None
    location_id: UUID | None
    purpose: str  # What happens, why it matters
    character_goals: dict[UUID, str]  # Character → what they want
    beats: list[str]  # Key events in order
    conflict: str  # What's at stake
    resolution: str  # How it ends
    status: "planned" | "in_progress" | "complete"
```

**Integration with writing:**
- Plans visible in Editor sidebar
- Beats checklist (check off as written)
- Plan status updates automatically
- Compare plan vs actual in Storyboard (PLAN-005)

**AI-assisted planning:**
- Generate beats from purpose statement
- Suggest conflicts based on character goals
- Identify missing beats (what's unaddressed)

## Constraints & Edge Cases

- No required fields — plan as much or little as you want
- Plans are flexible — change them anytime
- No validation that plan matches actual writing
- AI suggestions require LLM availability
- Very detailed plans may slow discovery writing
- Pantsers may prefer minimal planning

## Related Features

- [PLAN-003](PLAN-003-structure.md) — Chapter-level structure
- [PLAN-005](PLAN-005-storyboard.md) — Plan vs actual comparison
- [WRITE-002](../writing/WRITE-002-new-chapter.md) — Generate from plan
- [ASSIST-001](../ai_assist/ASSIST-001-plot-check.md) — Plot guidance

## Status & History

- `project-init` — Added to registry as planned feature
