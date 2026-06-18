---
id: PLAN-004
title: "Timeline Management"
status: stable
area: planning
mvp: false
architecture: PLAN-004-architecture.md

ui_tooltip: "Track story time, character ages, and event chronology."
ui_help_short: |
  Keep your story's timeline straight. Timeline Management tracks when events
  happen, character ages, and temporal relationships — catching
  inconsistencies and impossible dates.
ui_help_long: |
  ## Timeline Management

  Track when everything happens in your story world. Timeline Management
  ensures temporal consistency and catches impossible dates.

  **What gets tracked:**

  **Story Timeline**
  - When each chapter takes place
  - Time gaps between scenes
  - Overall story duration
  - Flashback/forward tracking

  **Character Timelines**
  - Birth dates and ages
  - Backstory events
  - Age consistency checks
  - Birthday tracking

  **Event Timeline**
  - Major story events in order
  - Cause-and-effect relationships
  - Simultaneous events
  - Prequel/sequel connections

  **Consistency Checking**
  - Impossible age calculations
  - Events before character birth
  - Conflicting dates
  - Duration impossibilities

  **How it works:**
  1. Open Planning panel
  2. Click "Timeline"
  3. Timeline view shows:
     - **Chronological view**: Events in time order
     - **Chapter view**: When each chapter happens
     - **Character view**: Each character's timeline
     - **Consistency**: Flagged issues
  4. Add events manually:
     - Date, time, description
     - Involved characters
     - Chapter reference
  5. Auto-extract from chapters:
     - Time expressions ("three days later")
     - Character ages
     - Explicit dates
  6. See inconsistencies flagged in red
  7. Click for explanation and fix suggestions

  **Timeline features:**
  - Multiple timelines (past, present, future)
  - Relative time ("three years before Chapter 1")
  - Duration calculation ("how long between X and Y?")
  - Export timeline as report

  **Best practices:**
  - Set timeline in chapter frontmatter
  - Add major events as you write
  - Run consistency check before publishing
  - Use relative time for flexibility

  **Use cases:**
  - Catch "character would be 150 years old"
  - Ensure flashbacks make sense
  - Track multiple storylines
  - Plan prequels/sequels

  Timeline data lives in Knowledge Base (KB-001, timeline entities) and chapter
  frontmatter. Keep it updated to avoid temporal headaches.

  Available in Planning panel, KB editor, or via CLI.
ui_available_in: [planning, kb]

service: planning/timeline_service.py
contract: planning/contracts.py#TimelineServiceProtocol
router: planning/router.py → GET /planning/timeline/{novel_id}
prompt: ADR-048 Mode 2 (agent-internal — no bundled cascade prompt)
requires: [KB-001, INFRA-001, INFRA-002]

core_agent: agents/timeline_agent.py (TimelineAgent)
---

# PLAN-004 — Timeline Management

## What it does

Temporal tracking system for story events, character ages, and chapter timing.
Auto-extracts time expressions from chapters, validates consistency, and flags
impossible dates or age contradictions.

## Why it exists

Readers notice timeline errors. Characters age inconsistently, events happen
in impossible orders, durations don't add up. Timeline management catches
these inconsistencies before publication.

## How it works (User perspective)

1. Open Planning panel → Timeline
2. Timeline shows multiple views:
   - **Chronological**: All events in time order
   - **By Chapter**: When each chapter happens
   - **Per Character**: Each character's timeline
   - **Consistency**: Flagged issues
3. Add events:
   - Click "Add Event"
   - Enter date, time, description
   - Select involved characters
   - Link to chapter if applicable
4. Auto-extract from chapters:
   - Click "Extract Timeline"
   - AI finds temporal expressions
   - Review and accept/reject
5. See inconsistencies flagged:
   - Click for explanation and fix
6. Export timeline as PDF

Timeline data comes from chapter frontmatter (timeline_position) and KB
timeline entries.

## How it works (Technical)

**Entry point:** `planning/router.py` → `GET /planning/timeline/{novel_id}`
**Service:** `TimelineService` in `planning/timeline_service.py`
**Contract:** `TimelineServiceProtocol` in `planning/contracts.py`
**Core Agent:** `TimelineAgent` in `core/agents/timeline_agent.py`
**Prompts:** ADR-048 Mode 2 — `TimelineAgent` composes its prompt internally from `TimelineDeps`. No bundled cascade prompt; user cannot override via PromptComposer.
**Storage:** KB timeline entries + chapter frontmatter + chapter summaries

**Flow:**
1. Router validates novel existence via `NovelRepository`
2. Resolves model config via `ModelRoutingResolver` using `LLMIntent.PLAN`
3. Instantiates `TimelineService` (in `planning/timeline_service.py`)
4. Service gathers chapters with summaries from `ChapterRepository`
5. Builds `TimelineDeps` with novel metadata (genre, language)
6. Runs `TimelineAgent` (in `core/agents/timeline_agent.py`)
7. Agent returns `TimelineOutput` with events, conflicts, and gaps
8. Service maps output to `TimelineResponse` schema

**Core Agent:** `TimelineAgent` — `NarrareAgent[TimelineDeps, TimelineOutput]`
- Deps: `TimelineDeps` — `genre`, `language`, optional `context_assembler`
- Output: `TimelineOutput` — list of `TimelineEvent`, `temporal_conflicts`, `coverage_gaps`, `overall_assessment`
- Event: `TimelineEvent` — event_name, description, timestamp, chapter_reference, characters_involved, location, causes, consequences
- Uses Output Function pattern (`_process_output`) for structured generation

**Timeline output:**
```python
class TimelineEvent(BaseModel):
    event_name: str
    description: str
    timestamp: str  # Relative or absolute time reference
    chapter_reference: str  # Chapter name or number
    characters_involved: list[str]
    location: str
    causes: list[str]
    consequences: list[str]
```

**Consistency checks (AI-powered):**
- Temporal conflicts: impossible ordering, contradictory time references
- Coverage gaps: missing causal links, unexplained time jumps
- Overall assessment: 1-2 sentence evaluation of timeline quality

## Constraints & Edge Cases

- Requires consistent date format in frontmatter
- Relative times ("Chapter 1 + 3 days") need reference point
- Flashbacks/forwards complicate ordering
- Ambiguous expressions ("later that summer") = low confidence
- Time zones and calendar systems not supported
- Fantasy time systems not handled (use relative time)
- Manual entry required for non-standard expressions

## Related Features

- [KB-001](../kb/KB-001-entity-management.md) — Timeline entities in KB
- [KB-007](../kb/KB-007-extraction.md) — Fact extraction
- [PLAN-005](PLAN-005-storyboard.md) — Storyboard view (uses `timeline_position` field for chronological context in stage layout)
- [CONS-001](../consistency/CONS-001-checker.md) — Temporal consistency checks
- [ADR-050](../../architecture/decisions/ADR-050-cross-feature-context-contracts.md) — Cross-feature ref lifecycle contract. Timeline is a `TimelineRefConsumer` of KB entity lifecycle events (rename / deprecate / delete). The hybrid JSON `{id, name}` refs in `timeline_events.character_refs` and `timeline_events.location_ref` are updated on rename, marked `status: "deprecated"` on deprecate, and surfaced as `RefIntegrityIssue` on hard delete.

## Timeline Integration Point

The `timeline_position` field on chapters is available for the storyboard's
chronological context. PLAN-005 Storyboard uses `chapter.position` (sequential
ordering) for stage assignment, but the `timeline_position` field provides
optional temporal metadata that future timeline features can build on.

**What exists now:**
- `timeline_position` field in chapter data model (available for chronological context)
- Storyboard (PLAN-005) uses chapter position for structure stage assignment

**Phase 4 implemented (AI timeline analysis):**
- ✅ AI-powered timeline analysis via `TimelineAgent` — chronological ordering, temporal conflict detection, coverage gap analysis
- ✅ Timeline prompt: ADR-048 Mode 2 (agent-internal from `TimelineDeps`)
- ✅ `GET /planning/timeline/{novel_id}` endpoint in `planning/router.py`
- ✅ TimelineService with chapter summary gathering + TimelineAgent invocation

**All phases implemented ✅** — See [PLAN-004-architecture.md](PLAN-004-architecture.md) for full details of the 3-phase implementation.
- Phase 1: TimelineEvent DB → CRUD endpoints → frontend display (TimelinePanel, EventList/Card/Form, AnalysisView)
- Phase 2: TemporalExtractionAgent + prompts (3 locales) → deterministic consistency checks → extraction/consistency endpoints → frontend review UI
- Phase 3: Character ages (KB metadata JSONB) → CSS timeline visualization (chronological, per-character, by-chapter) → cause→consequence links

## Architecture

Full architecture spec: [PLAN-004-architecture.md](PLAN-004-architecture.md)

Covers all 6 sub-features with phased implementation:
- **Phase 1:** Foundation (DB model + CRUD + display)
- **Phase 2:** AI features (auto-extraction + consistency)
- **Phase 3:** Advanced (character ages + visualization)

Key decisions: hybrid planning table with KB references, separate
TemporalExtractionAgent, KB metadata for birth dates, split consistency
engine (deterministic core + LLM backend).

## Status & History

- `project-init` — Added to registry as planned feature
- `2026-05-20` — Updated: noted `timeline_position` integration point with storyboard (PLAN-005). Status changed to in-progress (integration point only).
- `2026-05-31` — Phase 4 extension: AI-powered timeline analysis implemented (TimelineAgent, TimelineService, timeline prompts in 3 locales, `GET /planning/timeline/{novel_id}` endpoint). Frontmatter updated: service path corrected, router path corrected, core agent + prompts referenced. Status remains in-progress (analysis implemented, full timeline management still future work).
- `2026-06-01` — PLAN-004 Phase 3: Character age reading from KB metadata (JSONB, no migration), CharacterAgeCheck (deterministic), CSS timeline visualization with 3 views (chronological, by chapter, by character) with cause→consequence links. TimelineVisualization component + character ages panel. 59 tests.
- `2026-06-01` — PLAN-004 Phase 2: TemporalExtractionAgent (core agent + 3-locale prompts), deterministic consistency checks (TemporalOrderingCheck, DuplicateEventCheck), extraction + consistency endpoints, frontend review UI (TimelineExtractionReview + TimelineConsistencyPanel). 75 backend + 50 frontend tests.
- `2026-06-01` — PLAN-004 Phase 1: TimelineEvent DB model + Alembic migration, CRUD endpoints, frontend (TimelinePanel, EventList, EventCard, EventForm, AnalysisView), PlanningPanel tab in EditorView. 28 unit + 11 integration + 23 frontend tests.
- `2026-06-01` — Full architecture spec created (`PLAN-004-architecture.md`). Status changed to `architecture-review`. Covers all 6 sub-features across 3 phases. Key decisions: hybrid `timeline_events` table in planning module, separate `TemporalExtractionAgent`, KB `metadata_` for character birth dates, deterministic+LLM consistency engine following ADR-021.
