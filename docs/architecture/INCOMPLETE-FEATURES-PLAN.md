---
id: INCOMPLETE-FEATURES-PLAN
title: "Incomplete Features Remediation Plan"
status: active
area: architecture
mvp: false
date_created: 2026-06-10
last_updated: 2026-06-29
source: INCOMPLETE-FEATURES.md
---

# Incomplete Features Remediation Plan

> **Purpose:** Prioritized implementation plan for all 13 incomplete features (IF-01
> through IF-13) catalogued in `INCOMPLETE-FEATURES.md`. Groups findings into four
> actionable waves based on dependency analysis, effort estimation, and risk.
>
> **Audience:** Coordinator, Implementation Specialists, Architecture Specialist.
>
> **Source of truth:** `docs/architecture/INCOMPLETE-FEATURES.md`

---

## Executive Summary

The Narrare codebase is at Phase 6 (Post-MVP Features) with ~8,300+ backend tests,
~2,300 frontend tests, and 55 ADRs. Six incomplete features remain.

**Key change since last review (2026-06-10):** INFRA-007 was implemented (2026-06-29),
deploying the TaskIQ broker (Redis transport + result backend), Docker Compose worker
service, monitoring API, and 7 registered tasks. This **removes the infrastructure
blocker** for Wave C. Wave C items (IF-01, IF-02) are now blocked only on task logic
implementation and event mapping — not on worker infrastructure.

| Wave | Theme | Items | Sessions | Blocked |
|------|-------|-------|----------|---------|
| A | Quick Wins | IF-03, IF-08, IF-04 | 2-3 | No |
| B | Feature Completion | IF-05, IF-06, IF-12, IF-13 | 4-6 | No |
| C | Infrastructure | IF-01, IF-02 | 6-10 | **Partially** — infra exists, task logic missing |
| D | Future Enhancements | IF-09, IF-10, IF-11, IF-07 | Untimed | No |

---

## Dependency Graph

```
IF-01 (Task stubs — logic not implemented)
  |
  v
IF-02 (Event dispatch — empty map, inactive listener)
     depends on IF-01

IF-03 (Settings cascade)    ✅ RESOLVED
IF-04 (Embedding metadata)  ✅ RESOLVED
IF-05 (KB provenance)       ✅ RESOLVED
IF-06 (KB suggested ctx)    ✅ RESOLVED
IF-07 (Wiki core stub)      — independent, intentional design
IF-08 (Chat project_id)     ✅ RESOLVED
IF-09 (Arc types)           — independent, future ANAL-002
IF-10 (NRC EmoLex)          — independent, data + impl
IF-11 (Embedding Tier 2)    — independent, provider API
IF-12 (Name gen KB save)    ✅ RESOLVED
IF-13 (Doc placeholders)    ✅ RESOLVED
```

### Dependency Table

| Item | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| IF-01 | Task logic implementation (infra exists via INFRA-007) | IF-02 | C |
| IF-02 | IF-01 implementation + event mapping + lifespan wiring | Nothing | C |
| IF-03 | Nothing | Nothing | A ✅ |
| IF-04 | Nothing | Nothing | A ✅ |
| IF-05 | Nothing | Nothing | B ✅ |
| IF-06 | Nothing | Nothing | B ✅ |
| IF-07 | Nothing | Nothing | D |
| IF-08 | Nothing | Nothing | A ✅ |
| IF-09 | Nothing | Nothing | D |
| IF-10 | Nothing | Nothing | D |
| IF-11 | Nothing | Nothing | D |
| IF-12 | Nothing | Nothing | B ✅ |
| IF-13 | Nothing | Nothing | B ✅ |

---

## Wave A: Quick Wins (✅ COMPLETE)

All three Wave A items (IF-03, IF-08, IF-04) were resolved 2026-06-10.

---

## Wave B: Feature Completion (✅ COMPLETE)

All four Wave B items (IF-05, IF-06, IF-12, IF-13) were resolved 2026-06-10.

---

## Wave C: Infrastructure (Task Logic Implementation)

> **Status update (2026-06-29):** TaskIQ worker infrastructure is NOW DEPLOYED via
> INFRA-007 (broker, worker, monitoring, Docker Compose). All four Wave C prerequisites
> are met. The remaining work is implementing the actual task logic and wiring the event
> dispatch.

**Rationale:** These items implement the last mile of the background task pipeline.
The TaskIQ worker infrastructure (broker, worker process, monitoring) is deployed.
The tasks are decorated with `@broker.task` and accept typed events. What remains is:

1. IF-01: Replace stub bodies with real logic (mem0.add(), PreferenceAnalysisService)
2. IF-02: Populate `_EVENT_TASK_MAP` and wire listener into application lifespan

**Estimated sessions:** 4-6 (reduced from 6-10 since infra is done)

**Prerequisites (all met ✅):**
- [x] TaskIQ worker process deployed (Docker Compose service — INFRA-007)
- [x] TaskIQ broker configured (Redis-based per ADR-007)
- [x] Task health monitoring infrastructure available (GET /tasks/status — INFRA-007)
- [x] Worker can access PostgreSQL and Redis from its runtime environment (Docker Compose)

### C1: IF-01 -- TaskIQ Task Implementation (Replace Stubs)

- **ID:** IF-01
- **Layer:** Backend + Infrastructure
- **Effort:** Medium (~5 hours, reduced from ~8 since infra is done)
- **Priority:** High

**What:** Replace the two TaskIQ task stub bodies with real implementations.

**Current state (confirmed 2026-06-29):**
- Both tasks are properly decorated with `@broker.task(task_name=..., max_retries=3)`
- Both accept typed event objects (`FeedbackRecorded`, `PreferenceAnalysisTriggered`)
- Bodies are stubs: `logger.info("...", status="stub")` + TODO comments
- TaskIQ broker + worker are deployed and functional (INFRA-007)
- DI wiring for repositories/services is available in the API layer

**What remains:**

1. **`process_feedback_memory`**: Load `FeedbackEvent` from DB → translate to memory
   text (existing translation logic in `FeedbackService._translate_to_memory_text`) →
   call `mem0.add()` with user/project context.
   - DI: Needs `FeedbackEventRepository`, `mem0` client, `FeedbackService`
   - Risk: `mem0.add()` signature may differ from task expectations

2. **`run_preference_analysis`**: Create `PreferenceAnalysisService` via DI → call
   `service.analyze(user_id, project_id)` → persist results.
   - DI: Needs `PreferenceAnalysisService`, model registry, repos
   - Risk: Service expects `ModelRegistry` which may not be easily available in task context

**Files:**
- `apps/api/narrare/tasks/__init__.py` (primary change — replace stub bodies)
- Possibly new files: `tasks/feedback_memory.py`, `tasks/preference_analysis.py` (RULE-04)

**Tests:**
- Integration test with TaskIQ in-memory broker (available via taskiq's test utilities)
- Unit test: `process_feedback_memory` calls `mem0.add()` with correct arguments
- Unit test: `run_preference_analysis` creates service and calls `analyze()`
- Integration test: task health monitoring reports correct status after execution

**RULE-XX compliance:**
- RULE-04: Split into separate files if module exceeds 300 lines
- RULE-06: Each task file has one responsibility
- RULE-07: Tasks depend on services/repositories (correct direction)
- RULE-08: TaskIQ is abstracted behind the task interface
- RULE-11: Task failures are logged and retried, not silently swallowed

**References:** ADR-007 (TaskIQ), INFRA-007 (Background Tasks), INCOMPLETE-FEATURES.md IF-01

**Definition of Done:**
- [ ] `process_feedback_memory` body replaced: loads FeedbackEvent, calls mem0.add()
- [ ] `run_preference_analysis` body replaced: calls PreferenceAnalysisService.analyze()
- [ ] DI resolution strategy for task context documented (how services/repos are accessed)
- [ ] 3 tests pass (1 integration + 2 unit)
- [ ] INCOMPLETE-FEATURES.md IF-01 marked resolved

---

### C2: IF-02 -- Event Listener Dispatch

- **ID:** IF-02
- **Layer:** Infrastructure
- **Effort:** Medium (~3 hours, unchanged)
- **Priority:** High (depends on IF-01)

**What:** Wire the event listener to dispatch TaskIQ tasks. The `_dispatch` method
is implemented; the `_EVENT_TASK_MAP` is empty; the listener is not active.

**Current state (confirmed 2026-06-29):**
- `EventListener` class exists with `start()`, `listen()`, `stop()`, `_dispatch()` methods
- `_dispatch()` can enqueue via `broker.kiq()` if `_EVENT_TASK_MAP` has entries
- `_EVENT_TASK_MAP` is empty (only commented-out entries for chapter events)
- Listener is NOT wired into application lifespan
- Since INFRA-007: TaskIQ broker/worker exist, tasks are registered

**What remains:**

1. Populate `_EVENT_TASK_MAP` with at least one event-type-to-task mapping
   (e.g., `CHAPTER_CONTENT_UPDATED` → needs a registered chapter-embedding task)
2. Wire `EventListener` into application lifespan in `_app/lifespan.py`
3. Verify end-to-end: event published → listener receives → task enqueued → worker executes

**Prerequisite:** IF-01 must be at least partially implemented (tasks must do real work
before being wired into the event pipeline).

**Files:**
- `apps/api/narrare/_app/event_listener.py` (primary change — populate `_EVENT_TASK_MAP`)
- `apps/api/narrare/_app/lifespan.py` (wire listener startup/shutdown)

**Tests:**
- Integration test: publishing an event results in task enqueueing
- Integration test: event-to-task mapping routes to correct task function
- Unit test: dispatch failure is handled gracefully (logged, not raised)

**RULE-XX compliance:**
- RULE-07: Event listener depends on task layer (correct direction)
- RULE-08: Broker abstraction used, no direct Redis calls in listener
- RULE-11: Dispatch failures logged and handled, not silently swallowed

**References:** ADR-012 (Event-Driven Architecture), INFRA-007, INCOMPLETE-FEATURES.md IF-02

**Definition of Done:**
- [ ] `_EVENT_TASK_MAP` populated with at least one event-type-to-task mapping
- [ ] Listener wired into application lifespan (start on boot, stop on shutdown)
- [ ] End-to-end test: event → listener → task enqueueing → worker execution
- [ ] Error handling for dispatch failures in place
- [ ] 3 tests pass
- [ ] INCOMPLETE-FEATURES.md IF-02 marked resolved

---

## Wave D: Future Enhancements

**Rationale:** Low priority items with no immediate user impact. Some are intentionally
deferred (IF-09 depends on future ANAL-002 algorithm work), some require external data
or API access (IF-10, IF-11), and one represents an intentional design decision that
may not need to change at all (IF-07).

**Estimated sessions:** Untimed (opportunistic)

**Prerequisites:**
- [x] No blockers (except IF-09 which waits for ANAL-002)

### D1: IF-09 -- Typed Arc Segment Model

- **ID:** IF-09
- **Layer:** Core
- **Effort:** Small (~2 hours)
- **Priority:** Low

**What:** Replace `list[dict[str, object]]` with a typed `ArcSegment` Pydantic model in
the `NarrativeArc.segments` type annotation.

**When:** When the arc detection algorithm is implemented (ANAL-002 future work). Defining
the type now without the algorithm would be speculative.

**How:**
1. Define `ArcSegment` as a Pydantic model with fields for segment start, end, label,
   sentiment, and confidence score.
2. Update `NarrativeArc.segments` type annotation from `list[dict[str, object]]` to
   `list[ArcSegment]`.
3. Update any consumers that currently handle untyped dicts.

**Files:**
- `packages/core/narrare_core/analysis/types.py` (primary change)

**Tests:**
- Unit test: `ArcSegment` model validates correct data
- Unit test: `ArcSegment` model rejects invalid data

**References:** ANAL-002, INCOMPLETE-FEATURES.md IF-09

---

### D2: IF-10 -- NRC EmoLex Full Loading

- **ID:** IF-10
- **Layer:** Core
- **Effort:** Medium (~3 hours)
- **Priority:** Low

**What:** Implement full NRC Emotion Lexicon loading from data file, replacing the
`NotImplementedError`. Currently only a built-in subset is available.

**How:**
1. Obtain the NRC Emotion Lexicon data file (respect the attribution license requirements).
2. Include the data file in the package or document the download process.
3. Implement the parsing function to produce `dict[str, set[str]]` mapping words to
   emotion categories.
4. Cache the parsed result at module level for performance.
5. Ensure the built-in subset remains available as a fallback when the full lexicon is
   not installed.

**Files:**
- `packages/core/narrare_core/nlp/languages/emotions/__init__.py` (primary change)
- Possibly a new data file or download script

**Tests:**
- Unit test: full loading returns non-empty dictionary
- Unit test: loaded data maps known words to expected emotion sets
- Unit test: fallback to subset when full data unavailable

**References:** ANAL-002, INCOMPLETE-FEATURES.md IF-10

---

### D3: IF-11 -- Embedding Cascade Tier 2

- **ID:** IF-11
- **Layer:** Core
- **Effort:** Large (~6 hours)
- **Priority:** Low

**What:** Implement Tier 2 of the 4-tier embedding cascade: provider-native embeddings
for Anthropic and Google APIs. Currently the cascade skips Tier 2 (Tier 1: OpenAI ->
Tier 3: local -> Tier 4: disabled).

**How:**
1. Add a Tier 2 resolver that checks for Anthropic/Google embedding API availability
   based on user configuration.
2. Implement direct API calls to Anthropic and Google embedding endpoints.
3. Integrate Tier 2 into the existing cascade resolution order.
4. Add fallback behavior: if Tier 2 API is configured but fails, fall through to
   Tier 3 (local).

**Files:**
- `packages/core/narrare_core/memory/embedding_cascade.py` (primary change)
- Possibly new provider adapter files per RULE-04

**Tests:**
- Unit test: Tier 2 resolver returns provider embedding when API available
- Unit test: Tier 2 falls back to Tier 3 when API unavailable
- Unit test: Tier 2 falls back to Tier 3 on API error
- Integration test: full cascade resolution with all tiers configured

**References:** ADR-017 (superseded by ADR-033), ADR-033 (mem0 v3), INCOMPLETE-FEATURES.md IF-11

---

### D4: IF-07 -- Wiki Core Layer Enhancement

- **ID:** IF-07
- **Layer:** Core
- **Effort:** Small (~1 hour) -- but architectural decision needed first
- **Priority:** Low

**What:** Evaluate whether the core-layer wiki stub (`get_summaries()` returning empty dict)
should remain as-is or be replaced with a protocol + API-level implementation pattern.

**Note:** This is INTENTIONAL design. Core has no DB access per the project's layered
architecture. The stub exists because the core wiki service cannot directly query the
database. The question is whether introducing a protocol (similar to `KBSuggestedProvider`)
with an API-layer implementation would improve testability without violating the
no-DB-in-core constraint.

**Decision needed (one of):**
1. **Accept as-is** -- document the intentional design decision, close IF-07 as "by design"
2. **Protocol pattern** -- add `WikiSummaryProvider` protocol in core, implement in API
   layer, wire via DI. This improves testability of core consumers but adds an abstraction
   layer.

**If option 2 is chosen:**
- Create `WikiSummaryProvider` protocol in `packages/core/narrare_core/wiki/contracts.py`
- Implement in `apps/api/narrare/wiki/` layer
- Wire via DI in the pipeline that uses wiki summaries

**Files:**
- `packages/core/narrare_core/wiki/service.py` (if protocol pattern adopted)
- `packages/core/narrare_core/wiki/contracts.py` (new protocol, if adopted)

**Tests:**
- Unit test: mock provider returns wiki summaries, core consumer processes them

**References:** ADR-022 (LLM Wiki), WIKI-001, INCOMPLETE-FEATURES.md IF-07

---

## Blocked Items Register

The following items cannot proceed until prerequisites are met:

| ID | Item | Blocker | Resolution | Estimated Unblock |
|----|------|---------|------------|-------------------|
| IF-01 | TaskIQ Task Stubs | Task logic not implemented (infrastructure exists via INFRA-007) | Implement real task bodies with DI + mem0 + PreferenceAnalysisService | Next available session |
| IF-02 | Event Listener Dispatch | Depends on IF-01 (tasks must do real work first) + empty event map + inactive listener | Complete IF-01 first, then populate `_EVENT_TASK_MAP` and wire lifespan | After IF-01 |

**Updated reasoning (2026-06-29):** The TaskIQ worker infrastructure is NO LONGER
the blocker. INFRA-007 deployed the broker, worker, monitoring API, and Docker Compose
service. The tasks are already registered with `@broker.task` decorators. The remaining
blocker is implementing the stub bodies (loading data from DB, calling mem0, running
PreferenceAnalysisService) which requires DI-aware task factories.

---

## Decision Items Register

The following items require an explicit architectural decision before implementation:

| ID | Item | Decision Needed | Default Stance |
|----|------|----------------|----------------|
| IF-07 | Wiki Core Layer Stub | Accept as intentional design OR introduce protocol pattern | Accept as-is (document decision) |

**Process:** Register a decision in `docs/architecture/questions/` or as a short ADR
amendment. Do not start implementation until the decision is recorded.

---

## Statistics

### By Wave

| Wave | Items | Estimated Effort | Sessions | Blocked |
|------|-------|-----------------|----------|---------|
| A: Quick Wins | 3 | ~3.5 hours | 2-3 | ✅ Complete |
| B: Feature Completion | 4 | ~14 hours | 4-6 | ✅ Complete |
| C: Infrastructure | 2 | ~8 hours (revised down from ~11) | 4-6 | Partially — task logic |
| D: Future Enhancements | 4 | ~12 hours | Untimed | No |
| **Total** | **13** | **~37.5 hours** | **10-15+** | 2 blocked on implementation |

### By Layer (Remaining)

| Layer | Items | IDs |
|-------|-------|-----|
| Backend + Infrastructure | 2 | IF-01, IF-02 |
| Core | 3 | IF-09, IF-10, IF-11 |
| Architecture Decision | 1 | IF-07 |

### By Effort (Remaining)

| Effort | Count | IDs |
|--------|-------|-----|
| Small (<2 hours) | 2 | IF-07, IF-09 |
| Medium (2-4 hours) | 2 | IF-10, IF-02 |
| Large (4+ hours) | 2 | IF-01, IF-11 |

### Resolution Priority (Recommended Execution Order)

| Order | ID | Wave | Rationale |
|-------|----|------|-----------|
| 1 | IF-01 | C | Infrastructure exists — implement task logic next available session |
| 2 | IF-02 | C | Depends on IF-01 — wire event dispatch after tasks are real |
| 3-6 | IF-09, IF-10, IF-11, IF-07 | D | Opportunistic — no fixed order |

---

## Cross-Reference

This plan is derived from and must be kept in sync with:

| Document | Relationship |
|----------|-------------|
| `docs/architecture/INCOMPLETE-FEATURES.md` | Source inventory -- IF-01 through IF-13 |
| `docs/_shared/CURRENT_STATE.md` | Project phase and status (INFRA-007 status) |
| `docs/_shared/CONSTRAINTS.md` | RULE-XX compliance requirements |
| `docs/mvp/mvp-plan.md` | Phase 7 milestone (background task logic) |
| `docs/architecture/decisions/ADR-007-taskiq.md` | TaskIQ background tasks |
| `docs/architecture/decisions/ADR-012-event-driven.md` | Event-driven architecture |
| `docs/architecture/decisions/ADR-023-co-author-change-engine.md` | Co-author word limit |
| `docs/architecture/decisions/ADR-024-free-form-chat.md` | Chat history project_id |

---

## Maintenance

This document should be updated:

1. When an IF-XX item is resolved -- update the item's Definition of Done checklist,
   then mark the item as resolved in `INCOMPLETE-FEATURES.md`.
2. When a wave is completed -- update wave status and statistics.
3. When IF-01 implementation begins -- check if DI strategy for task context needs
   architectural decision (e.g., task-factory pattern vs. direct DI injection).
4. At each phase transition -- review all remaining items for priority changes.

---

> **Last reviewed:** 2026-06-29
> **Next review:** When IF-01 implementation begins, or at next phase transition
