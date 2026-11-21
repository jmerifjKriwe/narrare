---
id: PLAN-002
title: "Narrative Gap Analysis"
status: planned
area: planning
mvp: false

ui_tooltip: "Identify missing scenes, transitions, and unresolved plot threads."
ui_help_short: |
  Find narrative gaps before readers do. Gap Analysis identifies missing
  transitions, unresolved plot threads, absent KB entities, time jumps without
  scenes, and emotional gaps — then suggests scenes to fill them.
ui_help_long: |
  ## Narrative Gap Analysis

  Identify missing pieces in your story before readers notice. Gap Analysis
  finds holes in your narrative and suggests scenes to fill them.

  **What gets detected:**

  **Missing Transitions**
  - Location jumps without travel scenes
  - Time jumps without bridging scenes
  - POV switches without preparation
  - Abrupt scene endings

  **Unresolved Plot Threads**
  - Plotlines introduced but not resolved
  - Questions raised but not answered
  - Characters who disappear
  - Conflicts left hanging

  **Absent Entities**
  - Characters mentioned but never appear
  - Locations referenced but not shown
  - KB entities not used in story

  **Time Gaps**
  - Unexplained time jumps
  - Missing scenes between events
  - Timeline inconsistencies

  **Emotional Gaps**
  - Character reactions missing
  - Emotional beats skipped
  - Unearned emotional shifts

  **How it works:**
  1. Select chapters or entire novel
  2. Click "Gap Analysis" in Planning panel
  3. AI scans for gaps (15-45 seconds)
  4. Gaps grouped by severity:
     - **Critical**: Major gaps that confuse readers
     - **Moderate**: Significant gaps attentive readers notice
     - **Minor**: Small gaps most readers fill in
  5. For each gap, AI suggests:
     - Scene proposal (what would fill it)
     - Characters involved
     - Conflict/goal
     - Position in story
  6. Accept suggestions or ignore

  **Scene proposals include:**
  - Location suggestion
  - Character list
  - Scene goal
  - Conflict source
  - Emotional arc
  - Beat-by-beat outline
  - Word count estimate

  **Best practices:**
  - Run after major drafts or restructuring
  - Prioritize critical gaps
  - Use proposals as starting points, not prescriptions
  - Some gaps are intentional — know which are which

  **Use cases:**
  - Before beta readers (catch gaps early)
  - During revision (fill holes)
  - When stuck (identify what's missing)
  - After restructuring (find what broke)

  Not every gap needs filling. Some jumps are intentional, some mysteries are
  meant to persist. Gap analysis identifies options — you decide what's
  missing.

  Available in Planning panel or via CLI:
  `narrare planning gaps --novel <id>`
ui_available_in: [planning, cli]

service: planning/service.py
contract: planning/contracts.py#GapAnalysisProtocol
router: planning/router.py
prompt: core/prompts/_bundled/planning/en/gaps
requires: [INFRA-001, KB-001]
---

# PLAN-002 — Narrative Gap Analysis

## What it does

Identifies narrative gaps (missing transitions, unresolved threads, absent entities,
time jumps, emotional gaps) and generates scene proposals to fill them.
Severity-rated (Critical/Moderate/Minor) to prioritize fixes.

## Why it exists

Stories have holes. Writers introduce plot threads and forget them. Characters
disappear. Locations are referenced but never shown. Readers notice these gaps
and get frustrated. Gap analysis catches problems before readers do.

## How it works (User perspective)

1. Select chapters or entire novel
2. Click "Gap Analysis" in Planning panel
3. AI scans for narrative gaps (15-45 seconds)
4. Gaps appear grouped by severity:
   - 🔴 Critical: Confuses readers
   - 🟡 Moderate: Attentive readers notice
   - 🔵 Minor: Most readers fill in
5. Click any gap to see:
   - What's missing and why it matters
   - Scene proposal to fill it
   - Characters and location involved
   - Where it fits in story
6. Accept proposal to create plan, or ignore

Scene proposals can be converted to Scene Plans (PLAN-001) or written directly.

## How it works (Technical)

**Entry point:** `planning/router.py` → `POST /api/v1/planning/gaps`
**Service:** `GapAnalysisService.analyze()` in `planning/service.py`
**Contract:** `GapAnalysisProtocol` in `planning/contracts.py`
**LLM Intent:** `LLMIntent.PLAN`

**Gap detection:**
```python
class NarrativeGap:
    type: GapType  # transition, thread, entity, time, emotion
    severity: "critical" | "moderate" | "minor"
    description: str  # What's missing
    location: str  # Where in story (chapter/scene)
    proposal: SceneProposal | None  # How to fix
```

**Detection methods:**
- **Transition gaps**: Location/time changes without bridging scenes
- **Thread gaps**: Introduced plotlines not referenced again
- **Entity gaps**: KB entities mentioned but never appear
- **Time gaps**: Unexplained time jumps (>1 day without scene)
- **Emotional gaps**: Character reactions missing after events

**Scene proposal:**
```python
class SceneProposal:
    position: str  # Where this scene fits
    characters: list[UUID]  # Who's involved
    location: UUID | None  # Where it happens
    goal: str  # Scene purpose
    conflict: str  # What's at stake
    beats: list[str]  # What happens
    word_count: int  # Estimated length
```

## Constraints & Edge Cases

- Requires complete chapter outline (frontmatter or explicit)
- May flag intentional gaps (mysteries, implied scenes)
- Proposals are suggestions, not requirements
- Time gaps may be intentional (montage, ellipsis)
- Entity gaps assume KB is complete (may not be)
- Thread detection requires explicit introduction (not implied)
- LLM availability required

## Related Features

- [PLAN-001](PLAN-001-scene-planning.md) — Create scenes from proposals
- [PLAN-003](PLAN-003-structure.md) — Overall story structure
- [PLAN-005](PLAN-005-storyboard.md) — Plan vs actual tracking
- [KB-001](../kb/KB-001-entity-management.md) — Entity definitions

## Status & History

- `project-init` — Added to registry as planned feature
