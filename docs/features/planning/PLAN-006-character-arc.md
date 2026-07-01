---
id: PLAN-006
title: "Character Arc Analysis"
status: stable
area: planning
mvp: false

ui_tooltip: "Plan a character's development arc across the story."
ui_help_short: |
  Analyze a character's starting and goal states, then generates a multi-phase
  arc with turning points, internal conflict, and resolution.
ui_help_long: |
  ## Character Arc Analysis

  Plan how a character grows (or falls) across your story. Character Arc
  Analysis takes where a character begins, where they need to end up, and
  maps the journey between them — complete with turning points, key
  relationships, and internal conflict resolution.

  **Arc types supported:**
  - **Growth**: The character improves, overcomes flaws, becomes stronger
  - **Fall**: The character deteriorates, makes bad choices, loses their way
  - **Transformation**: The character fundamentally changes (not strictly better or worse)
  - **Flat**: The character stays consistent but changes the world around them

  **What you get:**
  - **Multi-phase arc**: 3-5 phases with name, description, emotional state, turning point, and suggested chapter range
  - **Key relationships**: Other characters who influence or are affected by the arc
  - **Internal conflict**: The psychological or emotional struggle driving the arc
  - **Resolution**: How the conflict resolves — triumph, tragedy, or ambiguity

  **How to use it:**
  1. Open Planning panel for your novel
  2. Click "Character Arc"
  3. Enter a character name, their current state, and their goal state
  4. Review the generated arc phases and relationships
  5. Refine by adjusting the starting/goal states and regenerating

  **Best practices:**
  - Be specific about the character's starting state ("afraid of public speaking" not "shy")
  - The goal state should be a meaningful transformation, not a trivial change
  - Use the chapter suggestions to plan when each phase unfolds
  - Combine with Timeline Analysis to ensure the arc pacing fits your story

  **Use cases:**
  - Plan a protagonist's hero journey
  - Design a villain's descent
  - Track supporting character growth across a series
  - Validate that each major character has a meaningful arc

  Character arc data lives in the planning module. For integration with
  timeline and story structure, see related features.
ui_available_in: [planning]

service: planning/character_arc_service.py
contract: planning/contracts.py#CharacterArcServiceProtocol
router: planning/router.py → POST /planning/character-arc/{novel_id}
prompt: ADR-054 Mode 1 (PromptComposer governed template via PLAN context_mode `character_arc` — user-overridable)
requires: [INFRA-001, INFRA-002, INFRA-003]
---

# PLAN-006 — Character Arc Analysis

## What it does

AI-powered character arc planning that generates a multi-phase development
arc (growth/fall/transformation/flat) with turning points, key relationships,
internal conflict, and resolution — given a character's starting and goal states.

## Why it exists

Characters are the heart of any story, but planning their emotional journey is
hard. Writers need a tool that helps them think through _how_ a character
changes, not just _what_ happens to them. This feature provides structured arc
planning that catches flat or inconsistent character development early.

## How it works (User perspective)

1. Open Planning panel → Character Arc
2. Enter character name, current state, and goal state
3. AI generates a multi-phase arc:
   - Phase name and description
   - Emotional state per phase
   - Key turning point that triggers each phase
   - Suggested chapter range for pacing
4. Review the output: key relationships, internal conflict, resolution
5. Refine inputs and regenerate as needed

## How it works (Technical)

**Entry point:** `apps/api/narrare/planning/router.py` → `POST /planning/character-arc/{novel_id}`

**Flow:**
1. Router validates novel existence
2. Resolves model via `ModelRoutingResolver` using `LLMIntent.PLAN`
3. Instantiates `CharacterArcService` (in `apps/api/narrare/planning/character_arc_service.py`)
4. Service builds deps with novel + character metadata
5. Runs `CharacterArcAgent` (in `packages/core/narrare_core/agents/character_arc_agent.py`)
6. Agent returns `CharacterArcOutput` with structured phases
7. Service maps output to `CharacterArcResponse` schema

**Core Agent:** `CharacterArcAgent` — `NarrareAgent[CharacterArcDeps, CharacterArcOutput]`
- Deps: `CharacterArcDeps` — `character_name`, `character_current_state`, `character_goal_state`, `genre`, `language`
- Output: `CharacterArcOutput` — multi-phase arc with relationships, conflict, resolution
- Output types: `ArcPhase` (phase_name, description, emotional_state, turning_point, chapters_suggested)
- Uses Output Function pattern (`_process_output`) for structured generation

**Prompts:** ADR-054 Mode 1 — `CharacterArcService` builds the feature prompt through `PromptComposer` (`PLAN` intent, `context_mode="character_arc"`), backed by the governed _bundled/planning/&lt;lang&gt;/character_arc/system.md template. `CharacterArcAgent` relays the composed prompt (it composes nothing itself — no `@agent.instructions`). The user *can* override the template via the cascade (project/user/bundled). (Previously mis-declared as ADR-048 Mode 2 "agent-internal"; that declaration was factually false — the agent owns no composition — and is removed by ADR-054 along with the inline f-string that preceded it.)

**Variables:**
- `{{character_name}}` — Character being analysed
- `{{character_current_state}}` — Starting emotional/situational state
- `{{character_goal_state}}` — Desired end state
- `{{genre}}` — Genre for arc-appropriate conventions
- `{{language}}` — Output language

**Service:** `CharacterArcService` in `apps/api/narrare/planning/character_arc_service.py`
- `generate_character_arc(novel_id, user_id, request) → CharacterArcResponse`
- Uses `NovelRepository` for novel metadata
- Uses `ModelRegistry.get_model()` for LLM model

## Constraints & Edge Cases

- Character must have a defined name — empty names return validation error
- Current/goal states are freetext — quality of output depends on specificity
- Arc types are AI-determined, not user-selectable (user can regenerate)
- Chapter suggestions are advisory — user decides actual pacing
- Limited to single-character arcs (no ensemble arc analysis yet)
- Complex multi-POV arcs may need iterative refinement across characters
- Requires novel metadata (genre, language) for context-appropriate arcs

## Related Features

- [PLAN-004](PLAN-004-timeline.md) — Timeline analysis for temporal arc pacing
- [PLAN-003](PLAN-003-structure.md) — Story structure for arc placement
- [PLAN-005](PLAN-005-storyboard.md) — Storyboard for arc visualisation
- [ANAL-007](../analysis/ANAL-007-voice-author.md) — Author voice profiling (character voice)
- [ANAL-008](../analysis/ANAL-008-voice-character.md) — Character voice consistency
- [CONS-001](../consistency/CONS-001-checker.md) — Character consistency checking

## Status & History

- `2026-05-31` — Created as part of Phase 6 prompt quality review (new core agent + service)
- `2026-05-31` — Status set to stable (backend-only, no UI yet)
