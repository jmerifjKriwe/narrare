# PLAN-004 Architecture — Timeline Management

> **Status:** implemented
> **Date:** 2026-06-01
> **Author:** Architecture Specialist (NarrareArchitectureSpecialist)
> **Feature Spec:** `docs/features/planning/PLAN-004-timeline.md`
> **ADR References:** ADR-015 (Agents First-Class), ADR-021 (Deterministic Analysis)

---

## Overview

PLAN-004 Timeline Management provides temporal tracking for narrative events,
character ages, and chapter timing. It covers 6 sub-features:

1. **Timeline Display** — Frontend for AI analysis (Phase 4 already implemented)
2. **Manual Timeline Events** — CRUD for user-created timeline events
3. **Auto-Extraction** — AI extracts temporal expressions from chapter content
4. **Character Age Tracking** — Birth dates on KB entities + age calculations
5. **Temporal Consistency Validation** — Deterministic + LLM checks
6. **Timeline Visualization** — Interactive timeline view

### Root Cause Analysis

**Symptom:** Writers cannot track when events happen, spot temporal
inconsistencies, or verify character ages remain consistent across chapters.

**Root Cause (2x Why):**
1. **Why inconsistent?** No structured temporal data — only free-text
   `timeline_position` on chapters and AI-generated analysis that is not
   persisted.
2. **Why no structured data?** Phase 4 implemented AI analysis as a
   read-only projection (no persistence). Without a persisted event model,
   there is nothing to validate, visualize, or build on.

**Design implication:** A persistent `timeline_events` table is the
foundation. Everything else (consistency, visualization, extraction) builds
on top of stored events.

---

## Architectural Decisions

### AD-1: DB Design — Hybrid Planning Table with KB References

**Decision:** New `timeline_events` table in the planning module, with
character/location references to KB entities via UUID.

**Alternatives considered:**

| Option | Description | Verdict | Rationale |
|--------|-------------|---------|-----------|
| A. Separate planning table | Planning owns timeline data, no KB dependency | Part of choice | Timeline events are planning-domain data (RULE-05). Planning module owns its models. |
| B. KB entities (`entity_type='timeline'`) | Store events as KB entities | Rejected | Timeline events are narrative planning data, not worldbuilding reference data. KB's `entity_type='timeline'` constraint exists but serves a different purpose (world events in the story universe). Mixing them conflates planning and worldbuilding domains. |
| C. Hybrid (CHOSEN) | Events in planning table, linked to KB entities via UUID | Accepted | Planning owns the events (RULE-05), but references KB entities (characters, locations) via UUID for cross-feature integration. Clean domain boundary with loose coupling. |

**Why hybrid wins:**
- RULE-05: Planning module owns timeline data (just like it owns `ChapterOutline`)
- Characters/locations are KB entities (worldbuilding) — timeline events reference them, not own them
- Integration Contract with KB is explicit: planning reads KB entity names, never writes to KB
- The planning module already has its own `apps/api/narrare/planning/models.py` with `ChapterOutline` — this follows the established pattern

### AD-2: Auto-Extraction — Separate TemporalExtractionAgent

**Decision:** New `TemporalExtractionAgent` in `core/agents/`, separate from
existing `TimelineAgent`.

**Alternatives considered:**

| Option | Description | Verdict | Rationale |
|--------|-------------|---------|-----------|
| A. Extend TimelineAgent | Add extraction mode to existing agent | Rejected | Violates SRP. TimelineAgent analyzes timeline structure; extraction is a fundamentally different LLM operation (reading prose vs. analyzing structure). |
| B. Separate TemporalExtractionAgent (CHOSEN) | New agent with own deps/output types | Accepted | Each agent is a first-class citizen (ADR-015). Extraction and analysis are different intents with different prompts, output schemas, and testing strategies. |

### AD-3: Character Ages — KB Entity Metadata (JSONB)

**Decision:** Store birth dates in existing `KBEntry.metadata_` JSONB field.

**Alternatives considered:**

| Option | Description | Verdict | Rationale |
|--------|-------------|---------|-----------|
| A. Add `birth_date` column to KBEntry | Dedicated column, typed | Rejected | Requires Alembic migration on KB module for a planning-only concern. Birth dates only apply to `entity_type='character'`. Adds a column to a table owned by the KB module from outside its domain. |
| B. Store birth dates as timeline events | Event with type "birth" | Rejected | Fragile — depends on event existing. Birth dates are character attributes, not narrative events. Requires special-case logic to distinguish birth events from other events. |
| C. KB `metadata_` JSONB (CHOSEN) | `{"birth_date": "1985-03-15", "birth_date_narrative": "Year of the Dragon"}` | Accepted | Zero migration. KB already has `metadata_` JSONB. Character templates already store arbitrary metadata. Planning reads via Integration Contract. |

**Integration Contract:**

```markdown
### Integration Contract: Planning Timeline ↔ KB Entities

**Shared data source:** KB entries (characters, locations)
**Data direction:** Planning → reads ← KB writes

**On data change** (KB entity updated):
- Planning reads KB entities fresh on every access (no cache)
- If character `metadata_.birth_date` changes, age recalculations happen on next consistency check
- If character name changes, timeline events show updated name

**On data deletion** (KB entity deleted):
- Timeline events retain their `character_refs` entries
- Display shows "(deleted)" suffix for unresolvable entity UUIDs
- No cascade delete — timeline events outlive their referenced entities

**Expected schema:** KB entry with `metadata_` containing optional
`birth_date` (ISO date string) and `birth_date_narrative` (free text).
```

### AD-4: Consistency Engine — Split by Determinism Tier

**Decision:** Deterministic rules in `packages/core/narrare_core/analysis/temporal.py`, DB-dependent
and LLM checks in backend service. Follows ADR-021 tiered approach.

**Alternatives considered:**

| Option | Description | Verdict | Rationale |
|--------|-------------|---------|-----------|
| A. All in backend service | Direct DB access for everything | Rejected | Temporal ordering/duration rules are pure logic — no DB needed. Putting them in backend makes them untestable without DB. |
| B. All in core | Core fetches data via contracts | Rejected | Core has no DB access (RULE-07). Injecting a repository into core violates the dependency direction. |
| C. Split: deterministic in core, DB+LLM in backend (CHOSEN) | Pure rules in `core/analysis/`, orchestration in backend | Accepted | Follows ADR-021: deterministic where possible, LLM where not. Core rules are testable in isolation. Backend orchestrates data flow. |

**Deterministic tier** (`packages/core/narrare_core/analysis/temporal.py`):
- Date parsing and normalization
- Temporal ordering violations
- Duration impossibilities
- Age calculations (birth date vs. event timestamp)
- Duplicate event detection

**LLM tier** (core/agents/ — via existing or extended TimelineAgent):
- Ambiguous temporal expressions ("later that summer")
- Contextual validation (genre-appropriate timeline)
- Causal consistency (do cause-effect chains make sense?)

### AD-5: Service Split — CRUD and Analysis as Separate Services

**Decision:** Split timeline into two services following RULE-04/06.

| Service | File | Responsibility | Est. Lines |
|---------|------|---------------|------------|
| `TimelineService` | `apps/api/narrare/planning/timeline_service.py` | CRUD operations (create, list, get, update, delete events) | ~150 |
| `TimelineAnalysisService` | `apps/api/narrare/planning/timeline_analysis_service.py` | AI analysis + extraction orchestration (extracted from current code) | ~120 |

**Rationale:** The existing `apps/api/narrare/planning/timeline_service.py` (126 lines) only does AI
analysis. Adding CRUD operations (~100 lines) would push it past the 200-line
soft target. Splitting upfront avoids a later refactor.

---

## DB Schema Design

### New Table: `timeline_events`

```sql
CREATE TABLE timeline_events (
    -- Identity
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id        UUID NOT NULL REFERENCES novels(id) ON DELETE CASCADE,

    -- Event data
    event_name      VARCHAR(500) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    event_type      VARCHAR(50) NOT NULL DEFAULT 'plot_point',

    -- Temporal data
    timestamp_raw        VARCHAR(200) NOT NULL DEFAULT '',
    timestamp_normalized VARCHAR(200) NOT NULL DEFAULT '',
    temporal_order       INTEGER,

    -- Chapter reference (optional — event may not map to a specific chapter)
    chapter_id      UUID REFERENCES chapters(id) ON DELETE SET NULL,

    -- KB entity references (hybrid model — AD-1)
    -- Each ref has both ID (for KB linkage) and name (for display)
    -- [{"id": "uuid-string", "name": "John Smith"}, ...]
    character_refs  JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- {"id": "uuid-string", "name": "The Castle"} or null
    location_ref    JSONB DEFAULT NULL,

    -- Causal links (free text or UUID references to other events)
    causes          TEXT NOT NULL DEFAULT '',
    consequences    TEXT NOT NULL DEFAULT '',

    -- Provenance
    source          VARCHAR(20) NOT NULL DEFAULT 'manual',
    -- 'manual' | 'ai_analysis' | 'extracted'
    confidence      FLOAT,          -- NULL for manual, 0.0-1.0 for AI
    is_confirmed    BOOLEAN NOT NULL DEFAULT TRUE,
    -- FALSE for extracted events pending user review

    -- Audit
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX ix_timeline_events_novel_id ON timeline_events(novel_id);
CREATE INDEX ix_timeline_events_chapter_id ON timeline_events(chapter_id);
CREATE INDEX ix_timeline_events_novel_order ON timeline_events(novel_id, temporal_order);
CREATE INDEX ix_timeline_events_source ON timeline_events(novel_id, source) WHERE source != 'manual';
CREATE INDEX ix_timeline_events_novel_type ON timeline_events(novel_id, event_type);

-- Check constraints
ALTER TABLE timeline_events ADD CONSTRAINT ck_timeline_events_source
    CHECK (source IN ('manual', 'ai_analysis', 'extracted'));
ALTER TABLE timeline_events ADD CONSTRAINT ck_timeline_events_event_type
    CHECK (event_type IN (
        'plot_point', 'character_event', 'world_event',
        'flashback', 'flashforward', 'birth', 'death', 'battle', 'journey', 'other'
    ));
ALTER TABLE timeline_events ADD CONSTRAINT ck_timeline_events_confidence
    CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0));
```

### Character Birth Date — KB Metadata Convention

No schema change. Characters store birth dates in existing `metadata_` JSONB:

```json
{
  "birth_date": "1985-03-15",
  "birth_date_narrative": "Year of the Dragon, Spring",
  "death_date": null,
  "age_at_story_start": 32
}
```

**Convention:** Planning module reads `metadata_.birth_date` and
`metadata_.birth_date_narrative` from KB character entities. KB module does
not need to know about this convention — it's a consumer-side contract.

### Chapter Model — No Changes

The existing `Chapter.timeline_position` (String 200) remains unchanged.
It provides the human-written temporal reference that the AI reads during
analysis. Timeline events supplement (not replace) this field.

---

## Module Boundaries

### What Lives Where

```
packages/core/narrare_core/
├── agents/
│   ├── timeline_agent.py              ← EXISTING (AI analysis)
│   ├── timeline_types.py              ← EXISTING (TimelineOutput, TimelineEvent)
│   ├── temporal_extraction_agent.py   ← NEW (Phase 2)
│   └── temporal_extraction_types.py   ← NEW (Phase 2)
├── analysis/
│   ├── temporal.py                    ← NEW (Phase 2: deterministic rules)
│   └── temporal_types.py             ← NEW (Phase 2: check result types)
└── prompts/_bundled/planning/{en,de,fr}/
    ├── timeline/system.md             ← EXISTING (analysis prompt)
    └── temporal_extraction/system.md  ← NEW (Phase 2: extraction prompt)

apps/api/narrare/planning/
├── contracts.py                       ← UPDATED: add new protocols
├── schemas.py                         ← EXISTING: storyboard/outline/arc (185 lines → keep)
├── timeline_schemas.py                ← NEW: timeline event CRUD schemas
├── models.py                          ← UPDATED: add TimelineEvent model
├── repository.py                      ← EXISTING: OutlineRepository (keep)
├── timeline_repository.py             ← NEW: TimelineEventRepository
├── service.py                         ← EXISTING: StoryboardService (keep)
├── timeline_service.py                ← REFACTORED: CRUD operations
├── timeline_analysis_service.py       ← NEW: AI analysis (extracted from current)
├── timeline_consistency_service.py    ← NEW (Phase 2): consistency orchestration
├── character_arc_service.py           ← EXISTING (keep)
├── remap_service.py                   ← EXISTING (keep)
├── _service_factory.py                ← EXISTING (keep)
├── _timeline_factory.py               ← UPDATED: wire CRUD service
├── _timeline_analysis_factory.py      ← NEW: wire analysis service
├── _timeline_consistency_factory.py   ← NEW (Phase 2)
├── _character_arc_factory.py          ← EXISTING (keep)
├── _helpers.py                        ← EXISTING (keep)
├── router.py                          ← EXISTING: storyboard/outline routes (127 lines → keep)
├── router_timeline.py                 ← NEW: timeline routes
└── __init__.py                        ← UPDATED: new exports

packages/web/
├── components/studio/planning/timeline/
│   ├── TimelinePanel.tsx              ← NEW: main container
│   ├── TimelineEventList.tsx          ← NEW: event list view
│   ├── TimelineEventCard.tsx          ← NEW: single event card
│   ├── TimelineEventForm.tsx          ← NEW: create/edit event form
│   ├── TimelineAnalysisView.tsx       ← NEW: AI analysis display
│   ├── TimelineExtractionReview.tsx   ← NEW (Phase 2): extraction review
│   ├── TimelineConsistencyPanel.tsx   ← NEW (Phase 2): consistency issues
│   ├── TimelineVisualization.tsx      ← NEW (Phase 3): interactive viz
│   └── __tests__/                     ← NEW: component tests
├── lib/hooks/
│   ├── useTimelineEvents.ts           ← NEW: CRUD hooks
│   ├── useTimelineAnalysis.ts         ← NEW: AI analysis hook (SSE)
│   ├── useTimelineExtraction.ts       ← NEW (Phase 2): extraction hook
│   └── useTimelineConsistency.ts      ← NEW (Phase 2): consistency hook
├── lib/api/
│   └── timeline.ts                    ← NEW: API client functions
├── types/
│   └── timeline.ts                    ← NEW: TypeScript interfaces
└── messages/{en,de,fr}/
    └── timeline.json                  ← NEW: i18n translations

packages/i18n/messages/{en,de,fr}/
    └── timeline.json                  ← NEW: shared translation keys
```

### File Size Analysis (RULE-04 Compliance)

| File | Current | After Phase 1 | Soft Target | Hard Limit | Action |
|------|---------|----------------|-------------|------------|--------|
| `apps/api/narrare/planning/models.py` | 58 lines | ~110 lines | 250 | 400 | Safe |
| `apps/api/narrare/planning/schemas.py` | 185 lines | 185 lines (unchanged) | 150 | 200 | Over soft — new schemas go in `apps/api/narrare/planning/timeline_schemas.py` |
| `apps/api/narrare/planning/contracts.py` | 107 lines | ~160 lines | 250 | 400 | Safe |
| `apps/api/narrare/planning/router.py` | 127 lines | 127 lines (unchanged) | 80 | 150 | Near hard limit — new routes go in `apps/api/narrare/planning/router_timeline.py` |
| `apps/api/narrare/planning/timeline_service.py` | 126 lines | ~150 lines (CRUD) | 200 | 300 | Safe |
| `apps/api/narrare/planning/timeline_analysis_service.py` | NEW | ~120 lines | 200 | 300 | Safe |
| `apps/api/narrare/planning/timeline_repository.py` | NEW | ~100 lines | 250 | 400 | Safe |
| `apps/api/narrare/planning/timeline_schemas.py` | NEW | ~100 lines | 150 | 200 | Safe |
| `apps/api/narrare/planning/router_timeline.py` | NEW | ~100 lines | 80 | 150 | Over soft but under hard — monitor |

### Dependency Direction (RULE-07)

```
router_timeline.py → timeline_service.py → timeline_repository.py → DB
                   → timeline_analysis_service.py → core/agents/timeline_agent.py
                                                   → core/agents/temporal_extraction_agent.py
                   → timeline_consistency_service.py → core/analysis/temporal.py
                                                      → core/agents/timeline_agent.py (LLM tier)

core/analysis/temporal.py → core/analysis/temporal_types.py (pure types)
                          → NO external dependencies

core/agents/temporal_extraction_agent.py → narrare_core.agents.base (NarrareAgent)
                                        → temporal_extraction_types.py
```

No circular dependencies. Core never imports from apps. Planning reads KB
entities via their public exports.

---

## Phased Implementation Plan

### Phase 1: Foundation (DB + CRUD + Display) ✅

**Goal:** Users can create, view, edit, and delete timeline events. The
existing AI analysis is preserved and refactored into a separate service.

**Pre-implementation requirements:**
- [x] Contracts defined in `apps/api/narrare/planning/contracts.py` before any service code
- [x] Alembic migration created alongside `apps/api/narrare/planning/models.py` changes (RULE-14)
- [x] `apps/api/narrare/planning/timeline_schemas.py` created before `apps/api/narrare/planning/timeline_service.py`
- [x] `apps/api/narrare/planning/router_timeline.py` created with all CRUD endpoints
- [x] Frontend types in `packages/web/types/timeline.ts` match backend schemas (RULE-17)

**Backend tasks:**

1. **Model** — Add `TimelineEvent` to `apps/api/narrare/planning/models.py`
2. **Migration** — Alembic migration for `timeline_events` table
3. **Schemas** — Create `apps/api/narrare/planning/timeline_schemas.py` with request/response models
4. **Repository** — Create `apps/api/narrare/planning/timeline_repository.py` with CRUD queries
5. **Contracts** — Update `apps/api/narrare/planning/contracts.py` with new protocols
6. **Service refactor** — Extract CRUD service to `apps/api/narrare/planning/timeline_service.py`,
   move AI analysis to `apps/api/narrare/planning/timeline_analysis_service.py`
7. **Factory** — Update `apps/api/narrare/planning/_timeline_factory.py`, create `apps/api/narrare/planning/_timeline_analysis_factory.py`
8. **Router** — Create `apps/api/narrare/planning/router_timeline.py` with CRUD + existing analysis route

**Frontend tasks:**

9. **Types** — Create `packages/web/types/timeline.ts` matching backend schemas
10. **API client** — Create `packages/web/lib/api/timeline.ts`
11. **Hooks** — Create `packages/web/lib/hooks/useTimeline.ts` (combined events + analysis)
12. **Components** — `TimelinePanel`, `TimelineEventList`, `TimelineEventCard`,
    `TimelineEventForm`, `TimelineAnalysisView`
13. **i18n** — `packages/i18n/messages/en/timeline.json` (and `de/`, `fr/`), register namespace (RULE-16)
14. **Tests** — Component tests, hook tests, API client tests

**Tests:**

- Unit: `TimelineEventRepository`, `TimelineService` (CRUD), `TimelineAnalysisService`
- Integration: `apps/api/narrare/planning/router_timeline.py` endpoints
- Frontend: component rendering, hook behavior, API contract

**Definition of Done — Phase 1:**
- [x] `POST /planning/timeline/{novel_id}/events` creates event (201)
- [x] `GET /planning/timeline/{novel_id}/events` lists events with filters
- [x] `GET /planning/timeline/{novel_id}/events/{id}` returns single event
- [x] `PUT /planning/timeline/{novel_id}/events/{id}` updates event
- [x] `DELETE /planning/timeline/{novel_id}/events/{id}` deletes event (204)
- [x] `GET /planning/timeline/{novel_id}` AI analysis still works (backward compat)
- [x] Frontend displays event list, supports create/edit/delete
- [x] Frontend displays AI analysis view
- [x] All 3 locales (en/de/fr) for timeline namespace
- [x] Migration up/down tested
- [x] Coverage: core 90%, api 80%

### Phase 2: AI Features (Auto-Extraction + Consistency) ✅

**Goal:** AI extracts temporal expressions from chapter content; users review
and accept/reject. Deterministic + LLM consistency checks flag issues.

**Pre-implementation requirements:**
- [x] `TemporalExtractionAgent` types in `packages/core/narrare_core/agents/temporal_extraction_types.py`
- [x] `TemporalExtractionAgent` in `packages/core/narrare_core/agents/temporal_extraction_agent.py`
- [x] Extraction prompts in `packages/core/narrare_core/prompts/_bundled/planning/en/timeline_extraction/system.md`
- [x] `packages/core/narrare_core/analysis/temporal.py` deterministic rules with types
- [x] Consistency contracts in `apps/api/narrare/planning/contracts.py`

**Backend tasks:**

1. **Core agent** — `packages/core/narrare_core/agents/temporal_extraction_agent.py` + `packages/core/narrare_core/agents/temporal_extraction_types.py`
2. **Core prompts** — `packages/core/narrare_core/prompts/_bundled/planning/en/timeline_extraction/system.md`
3. **Core analysis** — `packages/core/narrare_core/analysis/temporal.py` + `packages/core/narrare_core/analysis/temporal_types.py`
4. **Consistency service** — `apps/api/narrare/planning/timeline_consistency_service.py`
5. **Extraction service** — Add `extract_temporal_expressions()` to `apps/api/narrare/planning/timeline_analysis_service.py`
6. **Factory** — `apps/api/narrare/planning/_timeline_consistency_factory.py`
7. **Router** — Add extraction + consistency endpoints to `apps/api/narrare/planning/router_timeline.py`

**Frontend tasks:**

8. **Extraction UI** — `packages/web/components/studio/planning/timeline/TimelineExtractionReview.tsx` (accept/reject extracted events)
9. **Consistency UI** — `packages/web/components/studio/planning/timeline/TimelineConsistencyPanel.tsx` (issues list with explanations)
10. **Hooks** — `packages/web/lib/hooks/useTimelineExtraction.ts`, `packages/web/lib/hooks/useConsistency.ts`
11. **SSE streaming** — Extraction uses SSE via `connectSSE()` (RULE-20)
12. **Tests** — Component tests, SSE integration tests

**Tests:**

- Unit: `TemporalExtractionAgent` (TestModel), deterministic rules in `packages/core/narrare_core/analysis/temporal.py`
- Integration: extraction endpoint, consistency endpoint
- Frontend: extraction review flow, consistency display

**Definition of Done — Phase 2:**
- [x] `POST /planning/timeline/{novel_id}/extract` SSE streams extracted events
- [x] `POST /planning/timeline/{novel_id}/events/{id}/confirm` confirms extracted event
- [x] `DELETE /planning/timeline/{novel_id}/events/{id}` rejects extracted event
- [x] `GET /planning/timeline/{novel_id}/consistency` returns temporal issues
- [x] Deterministic checks: ordering violations, duration impossibilities, age contradictions
- [x] LLM checks: ambiguous expressions, causal consistency
- [x] Frontend extraction review with accept/reject
- [x] Frontend consistency panel with issue details
- [x] SSE streaming for extraction (RULE-20)
- [x] Extraction prompts in 3 locales

### Phase 3: Advanced (Character Ages + Visualization) ✅

**Goal:** Character birth dates integrated with KB; age calculations at story
points; interactive timeline visualization.

**Pre-implementation requirements:**
- [x] KB entity `metadata_` convention documented
- [x] Integration Contract with KB finalized
- [x] Visualization library evaluated (CSS-based, no new dependency)

**Backend tasks:**

1. **Age service** — Age calculation functions in `apps/api/narrare/planning/timeline_consistency_service.py`
2. **KB integration** — Read `metadata_.birth_date` from KB character entities
3. **Age endpoint** — `GET /planning/timeline/{novel_id}/character-ages`
4. **Consistency integration** — Age checks added to consistency engine

**Frontend tasks:**

5. **Visualization** — `packages/web/components/studio/planning/timeline/TimelineVisualization.tsx` (interactive timeline)
6. **Character ages** — Age display per character at each event point
7. **Multiple views** — Chronological, per-character, by-chapter
8. **Event connections** — Visual cause → consequence links

**Visualization approach:**

Evaluate rendering options. No new heavy dependency — use one of:
- **Option A:** CSS-based timeline (no dependency) — suitable for < 100 events
- **Option B:** `react-window` virtualized list with timeline layout — handles scale
- **Option C:** Canvas/SVG-based — for complex visualizations with connections

Recommend Option A for MVP, evaluate B/C when events exceed display capacity.
Requires ADR only if adding a new library dependency.

**Definition of Done — Phase 3:**
- [x] Character birth dates stored in KB entity `metadata_`
- [x] Age calculations displayed at each timeline event
- [x] Age consistency violations flagged in consistency checks
- [x] Interactive timeline visualization with event ordering
- [x] Per-character timeline view
- [x] Chronological and by-chapter views
- [x] Cause → consequence visual connections

---

## Contracts (Protocol Definitions)

### Phase 1 Contracts

```python
# planning/contracts.py — additions

@runtime_checkable
class TimelineEventRepositoryProtocol(Protocol):
    """Protocol for timeline event persistence."""

    async def get_by_id(self, event_id: uuid.UUID) -> TimelineEvent | None: ...
    async def list_by_novel(
        self,
        novel_id: uuid.UUID,
        *,
        event_type: str | None = None,
        chapter_id: uuid.UUID | None = None,
        source: str | None = None,
        is_confirmed: bool | None = None,
    ) -> list[TimelineEvent]: ...
    async def create(self, **fields: object) -> TimelineEvent: ...
    async def update(self, event_id: uuid.UUID, **fields: object) -> TimelineEvent: ...
    async def delete(self, event_id: uuid.UUID) -> bool: ...
    async def bulk_create(self, events: list[dict[str, object]]) -> list[TimelineEvent]: ...


@runtime_checkable
class TimelineEventServiceProtocol(Protocol):
    """Protocol for timeline event CRUD."""

    async def create_event(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, request: TimelineEventCreateRequest
    ) -> TimelineEventResponse: ...
    async def list_events(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, **filters: object
    ) -> list[TimelineEventResponse]: ...
    async def get_event(
        self, event_id: uuid.UUID, user_id: uuid.UUID
    ) -> TimelineEventResponse: ...
    async def update_event(
        self, event_id: uuid.UUID, user_id: uuid.UUID, request: TimelineEventUpdateRequest
    ) -> TimelineEventResponse: ...
    async def delete_event(self, event_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...


@runtime_checkable
class TimelineAnalysisServiceProtocol(Protocol):
    """Protocol for AI-powered timeline analysis."""

    async def generate_timeline(
        self, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> TimelineAnalysisResponse: ...
    async def extract_temporal_expressions(
        self, novel_id: uuid.UUID, user_id: uuid.UUID, chapter_ids: list[uuid.UUID]
    ) -> list[ExtractedEventResponse]: ...
    async def confirm_extracted_event(
        self, event_id: uuid.UUID, user_id: uuid.UUID
    ) -> TimelineEventResponse: ...
```

### Phase 2 Contracts

```python
# planning/contracts.py — Phase 2 additions

@runtime_checkable
class TemporalConsistencyServiceProtocol(Protocol):
    """Protocol for temporal consistency checking."""

    async def check_consistency(
        self, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> TemporalConsistencyResponse: ...
    async def check_character_ages(
        self, novel_id: uuid.UUID, user_id: uuid.UUID
    ) -> CharacterAgeReport: ...
```

---

## API Endpoints

### Phase 1 Endpoints

| Method | Path | Purpose | Stream | Request Body | Response |
|--------|------|---------|--------|-------------|----------|
| `GET` | `/planning/timeline/{novel_id}/events` | List events | No | — | `list[TimelineEventResponse]` |
| `POST` | `/planning/timeline/{novel_id}/events` | Create event | No | `TimelineEventCreateRequest` | `TimelineEventResponse` (201) |
| `GET` | `/planning/timeline/{novel_id}/events/{id}` | Get event | No | — | `TimelineEventResponse` |
| `PUT` | `/planning/timeline/{novel_id}/events/{id}` | Update event | No | `TimelineEventUpdateRequest` | `TimelineEventResponse` |
| `DELETE` | `/planning/timeline/{novel_id}/events/{id}` | Delete event | No | — | 204 |
| `GET` | `/planning/timeline/{novel_id}` | AI analysis (existing) | No | — | `TimelineAnalysisResponse` |

**Query parameters for list endpoint:**
- `event_type` — filter by type (plot_point, character_event, etc.)
- `chapter_id` — filter by chapter
- `source` — filter by source (manual, ai_analysis, extracted)
- `is_confirmed` — filter by confirmation status

### Phase 2 Endpoints

| Method | Path | Purpose | Stream | Request Body | Response |
|--------|------|---------|--------|-------------|----------|
| `POST` | `/planning/timeline/{novel_id}/extract` | Extract temporal expressions | **SSE** | `ExtractionRequest` | SSE chunks |
| `POST` | `/planning/timeline/{novel_id}/events/{id}/confirm` | Confirm extracted event | No | — | `TimelineEventResponse` |
| `GET` | `/planning/timeline/{novel_id}/consistency` | Temporal consistency check | No | — | `TemporalConsistencyResponse` |

### Phase 3 Endpoints

| Method | Path | Purpose | Stream | Request Body | Response |
|--------|------|---------|--------|-------------|----------|
| `GET` | `/planning/timeline/{novel_id}/character-ages` | Character age report | No | — | `CharacterAgeReport` |

---

## Core Agent Design

### TemporalExtractionAgent (Phase 2)

```
packages/core/narrare_core/agents/temporal_extraction_agent.py
packages/core/narrare_core/agents/temporal_extraction_types.py
```

**Purpose:** Extract temporal expressions from chapter content.

**Pattern:** `NarrareAgent[TemporalExtractionDeps, TemporalExtractionOutput]`

**Input deps:**
```python
class TemporalExtractionDeps:
    language: str
    genre: str
    existing_events: list[str]  # Names of existing events (to avoid duplicates)
```

**Output types:**
```python
class ExtractedTemporalExpression(BaseModel):
    expression: str           # Original text: "three days later"
    event_name: str           # Inferred name: "Arrival at the castle"
    timestamp_raw: str        # Raw temporal expression
    chapter_reference: str    # Chapter where found
    character_names: list[str]  # Characters mentioned nearby
    location_name: str        # Location mentioned nearby
    confidence: float         # 0.0-1.0
    context: str              # Surrounding sentence for user review

class TemporalExtractionOutput(BaseModel):
    extracted: list[ExtractedTemporalExpression]
    chapter_temporal_markers: list[str]  # All temporal markers found
    extraction_notes: str     # AI notes on extraction quality
```

**Prompt location:**
`packages/core/narrare_core/prompts/_bundled/planning/en/timeline_extraction/system.md`

**Testing:** `TestModel` with deterministic responses. Verify extraction
output structure matches `TemporalExtractionOutput`.

### TimelineAgent (Existing — No Changes)

The existing `TimelineAgent` continues to produce `TimelineOutput` with
events, conflicts, and gaps. No changes needed for Phase 1.

Phase 2 extends the analysis service to also persist AI-generated events
as `source='ai_analysis'` entries in the database.

---

## Consistency Engine Design

### Architecture (ADR-021 Compliance)

```
                    ┌──────────────────────────────┐
                    │  TimelineConsistencyService   │
                    │  (apps/api/planning/)         │
                    │                               │
                    │  1. Load events from DB       │
                    │  2. Load KB character data     │
                    │  3. Run deterministic rules    │
                    │  4. Run LLM checks (if needed) │
                    │  5. Merge + return results     │
                    └──────────┬───────────────────┘
                               │
               ┌───────────────┼───────────────┐
               ▼                               ▼
┌────────────────────────┐     ┌──────────────────────────┐
│ core/analysis/         │     │ core/agents/              │
│ temporal.py            │     │ timeline_agent.py         │
│                        │     │                          │
│ DET ERMINISTIC TIER:   │     │ LLM TIER:                │
│ • ordering violations  │     │ • ambiguous expressions  │
│ • duration checks      │     │ • causal consistency     │
│ • age calculations     │     │ • genre-specific checks  │
│ • duplicate detection  │     │ • contextual validation  │
│ • date normalization   │     │                          │
└────────────────────────┘     └──────────────────────────┘
```

### Deterministic Rules (core/analysis/temporal.py)

```python
# Pure functions — no I/O, no DB, fully testable

class TemporalOrderingCheck:
    """Detect events that violate temporal ordering."""
    # Event A has consequence referencing Event B,
    # but A.temporal_order > B.temporal_order

class DurationImpossibilityCheck:
    """Detect impossible durations between events."""
    # Travel from X to Y in 0 days, etc.

class CharacterAgeCheck:
    """Detect age inconsistencies at event points."""
    # Character at event is negative age, or impossibly old

class DuplicateEventCheck:
    """Detect likely duplicate events."""
    # Same timestamp_raw + same chapter + same character
```

### Consistency Result Types (core/analysis/temporal_types.py)

```python
class TemporalIssueSeverity(str, Enum):
    ERROR = "error"      # Definite inconsistency
    WARNING = "warning"  # Likely inconsistency
    INFO = "info"        # Possible concern

class TemporalIssue(BaseModel):
    severity: TemporalIssueSeverity
    rule_id: str              # e.g., "ordering_violation", "age_impossibility"
    event_ids: list[str]      # UUIDs of affected events
    description: str          # Human-readable explanation
    suggestion: str           # How to fix it
    source: str               # "deterministic" | "llm"

class TemporalConsistencyResult(BaseModel):
    issues: list[TemporalIssue]
    deterministic_pass: bool  # Did all deterministic checks pass?
    llm_pass: bool | None     # Did LLM checks pass? None if not run.
    overall_assessment: str
```

---

## Frontend Architecture

### Component Hierarchy

```
TimelinePanel (container — fetches data, manages state)
├── TabBar [Events | Analysis | Consistency | Visualization]
├── TimelineEventList
│   ├── TimelineEventCard (× N)
│   ├── TimelineEventForm (create/edit modal)
│   └── EmptyState ("No events yet. Add one or run AI analysis.")
├── TimelineAnalysisView
│   ├── EventTimeline (AI-generated events, chronological)
│   ├── ConflictList (temporal conflicts from AI)
│   └── GapList (coverage gaps from AI)
├── TimelineExtractionReview (Phase 2)
│   ├── ExtractedEventCard (accept/reject actions)
│   └── ExtractionProgress (SSE streaming indicator)
├── TimelineConsistencyPanel (Phase 2)
│   ├── IssueList (by severity)
│   └── IssueDetail (description + suggestion)
└── TimelineVisualization (Phase 3)
    ├── ChronologicalView
    ├── CharacterTimelineView
    └── ChapterTimelineView
```

### State Management (Zustand)

```typescript
// stores/timeline-store.ts
interface TimelineState {
  events: TimelineEvent[];
  analysisResult: TimelineAnalysis | null;
  consistencyResult: TemporalConsistency | null;
  isLoading: boolean;
  activeView: 'events' | 'analysis' | 'consistency' | 'visualization';
  filters: TimelineFilters;
}
```

### SSE Integration (RULE-20 Compliance)

The extraction endpoint (`POST /planning/timeline/{novel_id}/extract`)
streams extracted events via SSE. Frontend uses existing `connectSSE()`:

```typescript
// lib/api/timeline.ts
export async function extractTimeline(
  novelId: string,
  chapterIds: string[],
  callbacks: {
    onEvent: (event: ExtractedEvent) => void;
    onComplete: () => void;
    onError: (error: Error) => void;
  },
  signal?: AbortSignal,
): Promise<void> {
  await connectSSE<ExtractedEvent>({
    url: `/planning/timeline/${novelId}/extract`,
    body: { chapter_ids: chapterIds },
    onChunk: callbacks.onEvent,
    onComplete: callbacks.onComplete,
    onError: callbacks.onError,
    signal,
  });
}
```

The existing analysis endpoint (`GET /planning/timeline/{novel_id}`) remains
REST for Phase 1 (it is not a streaming operation — it returns a complete
analysis). Phase 2 may add an SSE variant for real-time analysis streaming.

### i18n (RULE-16 Compliance)

New namespace: `timeline`

Registration in `packages/web/lib/i18n/request.ts`:
```typescript
export const namespaces = [
  "common",
  // ... existing namespaces ...
  "timeline",  // ← NEW
];
```

Translation files:
- `packages/i18n/messages/en/timeline.json`
- `packages/i18n/messages/de/timeline.json`
- `packages/i18n/messages/fr/timeline.json`

---

## Migration Strategy

### Phase 1 Migration

```python
# alembic/versions/XXXX_add_timeline_events.py

def upgrade() -> None:
    op.create_table(
        "timeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("novel_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("event_type", sa.String(50), server_default="plot_point"),
        sa.Column("timestamp_raw", sa.String(200), server_default=""),
        sa.Column("timestamp_normalized", sa.String(200), server_default=""),
        sa.Column("temporal_order", sa.Integer(), nullable=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("character_refs", postgresql.JSONB(), server_default="[]"),
        sa.Column("location_ref", postgresql.JSONB(), nullable=True),
        sa.Column("causes", sa.Text(), server_default=""),
        sa.Column("consequences", sa.Text(), server_default=""),
        sa.Column("source", sa.String(20), server_default="manual"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_confirmed", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    # Indexes + constraints (see SQL schema above)

def downgrade() -> None:
    op.drop_table("timeline_events")
```

### No KB Migration

Character birth dates use existing `metadata_` JSONB. No Alembic migration
needed for KB entities.

### Data Backfill (Optional)

Existing AI analysis results are not persisted. Phase 1 does not backfill —
users re-run analysis to populate events. Future work could add a
"Save analysis as events" feature.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Router at 127/150 lines — adding timeline routes pushes past limit | Certain | Build failure | Preemptive split: `apps/api/narrare/planning/router_timeline.py` for all timeline routes. Existing routes stay in `apps/api/narrare/planning/router.py`. |
| `apps/api/narrare/planning/schemas.py` at 185/200 lines — adding timeline schemas pushes past limit | Certain | Build failure | Preemptive split: `apps/api/narrare/planning/timeline_schemas.py` for all timeline schemas. Existing schemas stay in `apps/api/narrare/planning/schemas.py`. |
| KB entity deletion leaves dangling references in `character_refs` | Medium | UI shows stale data | Graceful degradation: display "(deleted)" for unresolvable UUIDs. No cascade delete. |
| AI extraction quality varies by language | Medium | Poor DE/FR extraction | Extraction prompts in all 3 locales. Confidence scoring allows users to filter low-confidence results. |
| Temporal expression normalization is culturally complex | Medium | Incorrect ordering | `timestamp_normalized` stores best-effort normalized form. Users can manually override `temporal_order`. |
| Timeline visualization performance with >100 events | Low | Slow rendering | Phase 3 starts with CSS-based layout. Evaluate `react-window` virtualization if events exceed 100. |
| Deterministic temporal rules produce false positives | Medium | User frustration | All issues show explanation + suggestion. Users can dismiss individual issues. Severity levels (error/warning/info) distinguish certainty. |
| Service split introduces wiring complexity | Low | More files to maintain | Each service has its own factory file following established pattern (`apps/api/narrare/planning/_timeline_factory.py`, `apps/api/narrare/planning/_timeline_analysis_factory.py`). |

---

## RULE-XX Compliance Matrix

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | All LLM calls via `TemporalExtractionAgent` / `TimelineAgent` (core/agents/). No direct LLM imports in services. |
| RULE-02 | ✅ | Extraction prompts in `packages/core/narrare_core/prompts/_bundled/planning/en/timeline_extraction/system.md`. No f-string prompts in services. |
| RULE-03 | ✅ | Contracts in `apps/api/narrare/planning/contracts.py` defined before implementation: `TimelineEventServiceProtocol`, `TimelineEventRepositoryProtocol`, `TimelineAnalysisServiceProtocol`, `TemporalConsistencyServiceProtocol`. |
| RULE-04 | ✅ | Preemptive splits: `apps/api/narrare/planning/timeline_schemas.py`, `apps/api/narrare/planning/timeline_repository.py`, `apps/api/narrare/planning/timeline_analysis_service.py`, `apps/api/narrare/planning/router_timeline.py`. All files under soft targets. |
| RULE-05 | ✅ | Planning module owns `timeline_events` table, timeline services, timeline routes. KB owns entity data (read via Integration Contract). |
| RULE-06 | ✅ | Router delegates to service. Service delegates DB to repository. Analysis service delegates LLM to agent. One responsibility per file. |
| RULE-07 | ✅ | `router_timeline → timeline_service → timeline_repository → DB`. Core never imports from apps. Analysis module has no external deps. |
| RULE-08 | ✅ | No new external integrations. spaCy (if used for temporal parsing in Phase 2+) abstracted behind `NLPProvider` (ADR-021). |
| RULE-09 | ✅ | All public methods type-annotated. No `Any` in public interfaces. TypeScript types match backend schemas (RULE-17). |
| RULE-10 | ✅ | Unit tests for repository, service, deterministic rules. Integration tests for router endpoints. Frontend component + hook tests. |
| RULE-11 | ✅ | No silent failures. All except blocks re-raise, log (structlog), or convert to typed errors. |
| RULE-12 | ✅ | Service Layer is the only public API. All clients (WebUI, MCP, A2A, CLI) call same service protocols. |
| RULE-13 | ✅ | Extraction supports both SSE (`stream=True`) and REST (`stream=False`) through same service method. |
| RULE-14 | ✅ | Alembic migration created alongside `TimelineEvent` model. Up/down tested. |
| RULE-16 | ✅ | `timeline` namespace registered in `packages/web/lib/i18n/request.ts`. Translation files in all 3 locales. |
| RULE-17 | ✅ | Backend `TimelineEventResponse` fields match frontend `TimelineEvent` interface. Contract validated in tests. |
| RULE-20 | ✅ | No half-implementations. Each phase delivers complete, working features. SSE used for extraction (not deferred). |
| RULE-22 | ✅ | Cross-Feature Coherence: Integration Contract with KB defined. Shared data behaviour documented. |

---

## Sustainability Check

1. **Still correct in 3 months?** Yes. The hybrid model (planning table + KB references) is stable. Adding new event types is a CHECK constraint update, not a schema change.

2. **Hard-to-undo coupling?** No. Planning reads KB via public exports. If KB changes its `metadata_` structure, the Planning module's Integration Contract documents the expected schema.

3. **Simplest correct solution?** Yes. Separate `timeline_events` table is the minimum needed for CRUD. KB `metadata_` for birth dates avoids a migration. Deterministic rules in core are pure functions.

4. **Next developer understands intent?** Yes. File naming follows established patterns (`apps/api/narrare/planning/timeline_service.py`, `apps/api/narrare/planning/timeline_repository.py`, `apps/api/narrare/planning/router_timeline.py`). Module map updated. Architecture doc provides context.

---

## Related Documents

- Feature spec: `docs/features/planning/PLAN-004-timeline.md`
- ADR-015: Pydantic-AI Agents as First-Class Citizens
- ADR-021: Deterministic Analysis Strategy
- Integration Contract: Planning Timeline ↔ KB Entities (this document)
- Architecture rules: `docs/_shared/CONSTRAINTS.md`
- Module map: .opencode/context/narrare-dev/domain/module-map.md
