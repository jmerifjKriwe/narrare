---
id: INCOMPLETE-FEATURES-PLAN
title: "Incomplete Features Remediation Plan"
status: active
area: architecture
mvp: false
date_created: 2026-06-10
last_updated: 2026-06-10
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

The Narrare codebase is at Phase 6 (Post-MVP Features) with ~6,240+ tests and 43 ADRs.
Thirteen incomplete features remain, ranging from trivial placeholder fixes to
infrastructure-gated TaskIQ integration. This plan organizes them into four waves:

| Wave | Theme | Items | Sessions | Blocked |
|------|-------|-------|----------|---------|
| A | Quick Wins | IF-03, IF-08, IF-04 | 2-3 | No |
| B | Feature Completion | IF-05, IF-06, IF-12, IF-13 | 4-6 | No |
| C | Infrastructure | IF-01, IF-02 | 6-10 | Yes -- TaskIQ worker |
| D | Future Enhancements | IF-09, IF-10, IF-11, IF-07 | Untimed | No |

Wave A and B can begin immediately. Wave C is gated on the Phase 7 TaskIQ worker
milestone. Wave D items have no timeline and can be addressed opportunistically.

---

## Dependency Graph

```
IF-01 (TaskIQ stubs)
  |
  v
IF-02 (Event dispatch) --- depends on IF-01

IF-03 (Settings cascade)    --- independent, SET-005 exists
IF-04 (Embedding metadata)  --- independent
IF-05 (KB provenance)       --- independent, needs Alembic migration
IF-06 (KB suggested ctx)    --- independent, protocol exists
IF-07 (Wiki core stub)      --- independent, intentional design
IF-08 (Chat project_id)     --- independent, trivial
IF-09 (Arc types)           --- independent, future ANAL-002
IF-10 (NRC EmoLex)          --- independent, data + impl
IF-11 (Embedding Tier 2)    --- independent, provider API
IF-12 (Name gen KB save)    --- independent, full-stack
IF-13 (Doc placeholders)    --- independent, docs only
```

### Dependency Table

| Item | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| IF-01 | TaskIQ worker infrastructure (Phase 7) | IF-02 | C |
| IF-02 | IF-01 | Nothing | C |
| IF-03 | Nothing (SET-005 cascade exists) | Nothing | A |
| IF-04 | Nothing | Nothing | A |
| IF-05 | Nothing | Nothing | B |
| IF-06 | Nothing | Nothing | B |
| IF-07 | Nothing | Nothing | D |
| IF-08 | Nothing | Nothing | A |
| IF-09 | Nothing | Nothing | D |
| IF-10 | Nothing | Nothing | D |
| IF-11 | Nothing | Nothing | D |
| IF-12 | Nothing | Nothing | B |
| IF-13 | Nothing | Nothing | B |

---

## Wave A: Quick Wins

**Rationale:** High-value, independent, low-to-medium effort, no blockers. These items
close obvious gaps with minimal risk. Completing them first improves daily user experience
and reduces the noise in the INCOMPLETE-FEATURES register.

**Estimated sessions:** 2-3

**Prerequisites:**
- [ ] No external blockers
- [ ] SET-005 cascade infrastructure confirmed available (for A1)
- [ ] ChatService conversation loading confirmed (for A2)

### A1: IF-03 -- Settings Cascade for Co-Author Word Limit

- **ID:** IF-03
- **Layer:** Backend
- **Effort:** Small (~1 hour)
- **Priority:** High (ADR-023 gap)

**What:** Wire the SET-005 3-layer resolution cascade into the co-author word limit
validation in `coauthor_service.py`, replacing the hardcoded `max_words = 2000`.

**How:**
1. Locate the existing SET-005 cascade resolution pattern used by other writing services.
2. Import and inject the cascade resolver into `CoAuthorService` via dependency injection.
3. Replace lines 114-117 in `coauthor_service.py` with cascade resolution:
   `max_words = await self._settings_cascade.resolve(user_id, project_id, "max_coauthor_words", default=2000)`.
4. The resolution order is: user setting -> project setting -> default (2000).

**Files:**
- `apps/api/narrare/writing/coauthor_service.py` (primary change)
- `apps/api/narrare/writing/deps.py` (DI wiring for cascade resolver)

**Tests:**
- Unit test: cascade resolution returns user-level value when set
- Unit test: cascade resolution falls back to project-level value
- Unit test: cascade resolution returns default 2000 when no settings configured
- Unit test: validation still raises `ValidationError` when word count exceeds resolved limit

**RULE-XX compliance:**
- RULE-03: Contract for cascade resolver already exists (SET-005)
- RULE-06: Service owns logic, router delegates
- RULE-09: Full type annotations on new method

**References:** ADR-023 (Co-Author Change Engine), SET-005, INCOMPLETE-FEATURES.md IF-03

**Definition of Done:**
- [ ] Hardcoded `max_words = 2000` replaced with cascade resolution
- [ ] DI wiring complete in `deps.py`
- [ ] 4 unit tests pass
- [ ] INCOMPLETE-FEATURES.md IF-03 marked resolved

---

### A2: IF-08 -- Chat History Project ID

- **ID:** IF-08
- **Layer:** Backend
- **Effort:** Small (~30 min)
- **Priority:** Medium

**What:** Replace the `UUID(int=0)` placeholder in the chat history response with the
real project_id from the conversation entity.

**How:**
1. In `ChatService.get_history()` or `ChatRepository`, load the conversation entity to
   obtain the `project_id` associated with the conversation.
2. Pass `project_id` through to the `ChatHistoryResponse` constructor.
3. If the conversation has no associated project, use `UUID(int=0)` as a legitimate
   fallback with a comment explaining the semantics.

**Files:**
- `apps/api/narrare/chat/router.py` (primary change, line 99)
- `apps/api/narrare/chat/service.py` (may need method signature update)
- `apps/api/narrare/chat/repository.py` (query to load conversation with project_id)

**Tests:**
- Unit test: response contains correct project_id when conversation has a project
- Unit test: response falls back to zero UUID when conversation has no project

**RULE-XX compliance:**
- RULE-06: Router delegates to service for data retrieval
- RULE-11: No silent failure -- fallback is explicit and commented
- RULE-09: Full type annotations

**References:** CHAT-001, ADR-024 (Free-Form Chat), INCOMPLETE-FEATURES.md IF-08

**Definition of Done:**
- [ ] `UUID(int=0)` placeholder replaced with real project_id lookup
- [ ] Fallback behavior documented in code comment
- [ ] 2 unit tests pass
- [ ] INCOMPLETE-FEATURES.md IF-08 marked resolved

---

### A3: IF-04 -- Embedding Metadata Wire-Up

- **ID:** IF-04
- **Layer:** Backend
- **Effort:** Medium (~2 hours)
- **Priority:** Medium

**What:** Wire `usage_count` and `last_referenced_at` from KB entries into the
`ScoredCandidate` model so the hybrid scoring algorithm can use recency and usage
frequency signals for ranking.

**How:**
1. In `EmbeddingRepository.search()`, add a JOIN or subquery against the KB entries
   table to retrieve `usage_count` and `last_referenced_at` for matched candidates.
2. Pass the metadata through to `ScoredCandidate` construction in `EmbeddingService`.
3. Verify the hybrid scoring algorithm in the proactive context pipeline receives and
   applies the new signals correctly.

**Files:**
- `apps/api/narrare/embeddings/service.py` (primary change, lines 166-167)
- `apps/api/narrare/embeddings/repository.py` (JOIN/subquery addition)

**Tests:**
- Integration test: search results have non-zero `usage_count` for frequently referenced entries
- Integration test: search results have non-null `last_referenced_at` for referenced entries
- Unit test: `ScoredCandidate` construction with metadata values

**RULE-XX compliance:**
- RULE-06: Repository owns query logic, service owns orchestration
- RULE-07: Dependency direction maintained (service -> repository)
- RULE-09: Full type annotations on query results

**References:** INFRA-004 (Embedding Store), KB-005 (Proactive Context), INCOMPLETE-FEATURES.md IF-04

**Definition of Done:**
- [ ] `usage_count` populated from KB entries in search results
- [ ] `last_referenced_at` populated from KB entries in search results
- [ ] 3 tests pass (2 integration, 1 unit)
- [ ] INCOMPLETE-FEATURES.md IF-04 marked resolved

---

## Wave B: Feature Completion

**Rationale:** Medium effort, independent items that complete partially-implemented features.
These close functional gaps where the interface exists but the implementation is incomplete.
Each item is self-contained and can be worked in parallel.

**Estimated sessions:** 4-6

**Prerequisites:**
- [ ] No external blockers
- [ ] Alembic migration workflow available (for B1)
- [ ] ProactiveContextService accessible from core (for B2)
- [ ] Generation API endpoints reviewed (for B3)

### B1: IF-05 -- KB Extraction Provenance Fields

- **ID:** IF-05
- **Layer:** Core + Backend
- **Effort:** Medium (~3 hours)
- **Priority:** Medium

**What:** Add provenance fields (`source`, `review_status`) to the KB entry creation
schema and model. Wire them into the extraction apply service so auto-extracted entries
are distinguishable from manually created ones.

**How:**
1. Add `source: str` field to `KBEntryCreate` schema with default `"manual"`.
2. Add `review_status: str` field to `KBEntryCreate` schema with default `"approved"`.
3. Add corresponding columns to the `KBEntry` SQLAlchemy model.
4. Create Alembic migration for the new columns.
5. In `extraction_apply_service.py`, set `source="auto_extraction"` and
   `review_status="pending"` for entries created via extraction.
6. Add `review_status` filter parameter to the KB listing endpoint/repository.

**Files:**
- `apps/api/narrare/kb/schemas.py` (add provenance fields to `KBEntryCreate`)
- `apps/api/narrare/kb/models.py` (add columns to `KBEntry`)
- `apps/api/narrare/kb/extraction_apply_service.py` (wire provenance values)
- `apps/api/narrare/kb/repository.py` (add `review_status` filter)
- New Alembic migration file

**Tests:**
- Unit test: extraction service sets `source="auto_extraction"` and `review_status="pending"`
- Unit test: manual creation uses defaults `source="manual"` and `review_status="approved"`
- Integration test: DB migration applies successfully
- Integration test: KB listing filters by `review_status`

**RULE-XX compliance:**
- RULE-03: Schema changes are contract changes -- update `contracts.py` if protocol exists
- RULE-04: If `schemas.py` exceeds limits, split into `schemas_kb.py` / `schemas_extraction.py`
- RULE-06: Service owns logic, repository owns query
- RULE-09: Full type annotations on new fields

**References:** CR-AUFG-04-B3, KB-007 (Extraction), INCOMPLETE-FEATURES.md IF-05

**Definition of Done:**
- [ ] `KBEntryCreate` schema has `source` and `review_status` fields
- [ ] `KBEntry` model has corresponding columns
- [ ] Alembic migration created and tested
- [ ] Extraction sets provenance values correctly
- [ ] KB listing supports `review_status` filter
- [ ] 4 tests pass
- [ ] INCOMPLETE-FEATURES.md IF-05 marked resolved

---

### B2: IF-06 -- KB Suggested Context Provider

- **ID:** IF-06
- **Layer:** Core
- **Effort:** Medium (~3 hours)
- **Priority:** Medium

**What:** Replace the placeholder text `"[KB context will be provided in a future update]"`
with real KB context when a provider is available. The `KBSuggestedProvider` protocol
already exists but has no concrete implementation.

**How:**
1. Create `KBSuggestedProviderImpl` in a new file that wraps the existing
   `ProactiveContextService` from the backend layer.
2. Implement the protocol method to call the proactive context service and return
   formatted KB context.
3. Wire the implementation into the `InvocationPipeline` via dependency injection.
4. When no provider is configured (e.g., in core-only tests), gracefully degrade:
   log a warning and skip the enrichment step entirely rather than injecting a
   placeholder string.

**Files:**
- `packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py` (primary change)
- New implementation file (e.g., `kb_suggested_impl.py` or backend adapter)
- DI wiring in the relevant pipeline configuration

**Tests:**
- Unit test: mock provider returns real KB context, placeholder is not present in output
- Unit test: no provider configured -- enrichment step skipped, no placeholder in output
- Unit test: provider returns empty context -- graceful handling, no error

**RULE-XX compliance:**
- RULE-03: `KBSuggestedProvider` protocol already exists -- implementation follows contract
- RULE-07: Core defines protocol, backend provides implementation (correct dependency direction)
- RULE-08: External dependency (ProactiveContextService) is abstracted behind the protocol
- RULE-11: No silent failure -- missing provider is logged, not silently swallowed

**References:** CR-03 (AI Invocation), INFRA-013, INCOMPLETE-FEATURES.md IF-06

**Definition of Done:**
- [ ] `KBSuggestedProviderImpl` implements the protocol
- [ ] Placeholder text removed from production code path
- [ ] Graceful degradation when no provider is configured
- [ ] DI wiring complete
- [ ] 3 unit tests pass
- [ ] INCOMPLETE-FEATURES.md IF-06 marked resolved

---

### B3: IF-12 -- Name Generator Save to KB

- **ID:** IF-12
- **Layer:** Full-stack (Backend + Frontend)
- **Effort:** Medium (~4 hours)
- **Priority:** Low

**What:** Enable saving generated names as KB entries. The frontend button currently
logs to console. A backend endpoint and frontend integration are needed.

**How:**
1. **Backend:** Either create a new endpoint `POST /generation/names/{name_id}/save-to-kb`
   or reuse the existing `POST /novels/{novel_id}/kb` endpoint with appropriate schema
   adaptation. Evaluate which approach fits the existing generation module structure
   (RULE-06: router delegates, service owns logic).
2. **Frontend:** Replace `console.log` in `NameResults.tsx` line 37 with an actual API
   call using the project's standard fetch pattern (TanStack Query mutation or
   `useAIOperation`-compliant call per ADR-043).
3. Add loading state (spinner or disabled button) and success/error feedback using
   canonical `studio.aiActions.*` i18n keys (ADR-043 compliance).
4. Validate that the saved name appears in the KB browser.

**Files:**
- `packages/web/components/studio/generation/NameResults.tsx` (primary frontend change)
- `apps/api/narrare/generation/router.py` (possible new endpoint, evaluate first)
- `apps/api/narrare/generation/service.py` (save-to-KB logic)
- i18n files (en/de/fr) for success/error messages

**Tests:**
- Component test: save button triggers API call with correct payload
- Component test: loading state shown during API call
- Component test: success feedback shown on 200 response
- Component test: error feedback shown on failure
- Unit test: backend endpoint/service creates KB entry correctly

**RULE-XX compliance:**
- RULE-06: Router delegates to service, service owns save logic
- RULE-04: If router exceeds 150 lines, split into `router_generation.py` / `router_names.py`
- RULE-09: Full type annotations on new endpoint
- RULE-11: Error handling with user-visible feedback
- ADR-043: Use `useAIOperation` or canonical AI action pattern for API call

**References:** GEN-001, ADR-043 (useAIOperation Primitives), INCOMPLETE-FEATURES.md IF-12

**Definition of Done:**
- [ ] Backend endpoint or service method for save-to-KB implemented
- [ ] Frontend button calls API instead of console.log
- [ ] Loading state and success/error feedback implemented
- [ ] i18n keys added in all 3 locales
- [ ] 5 tests pass (4 component + 1 unit)
- [ ] INCOMPLETE-FEATURES.md IF-12 marked resolved

---

### B4: IF-13 -- Feature Spec Documentation

- **ID:** IF-13
- **Layer:** Documentation
- **Effort:** Medium (~4 hours total, spread across 4 specs)
- **Priority:** Documentation

**What:** Fill 36 `n:` placeholder markers across 4 feature specs. Each marker represents
a missing content section (tooltip, help text, description, implementation details,
limitations, related features).

**How:**
For each of the 4 specs, complete the following sections where `n:` markers appear:
1. **Tooltip:** Concise one-line description for UI tooltip display.
2. **Help text:** 2-3 sentence explanation for help overlay or documentation.
3. **Description:** Full feature description with user-facing behavior.
4. **Implementation details:** Technical description of how the feature works.
5. **Limitations:** Known limitations and edge cases.
6. **Related features:** Cross-references to related feature specs.

**Files:**
- `docs/features/setup/SETUP-003-import.md` (9 markers)
- `docs/features/io/IO-001-export.md` (9 markers)
- `docs/features/io/IO-002-import.md` (9 markers)
- `docs/features/io/IO-003-sync.md` (9 markers)

**No tests needed** -- documentation only.

**RULE-XX compliance:**
- RULE-20 (no stubs, no half-implementations): `n:` markers are documentation stubs that
  must be resolved before the affected features reach status:stable.

**References:** INCOMPLETE-FEATURES.md IF-13, Section 4

**Definition of Done:**
- [ ] All 36 `n:` markers replaced with real content across 4 specs
- [ ] Content follows the documentation style guide
- [ ] Cross-references between specs are accurate
- [ ] Specs pass the Documentation Gate review
- [ ] INCOMPLETE-FEATURES.md IF-13 marked resolved

---

## Wave C: Infrastructure (Milestone-Gated)

**Rationale:** These items are blocked on TaskIQ worker infrastructure, which is a
Phase 7 milestone. The event-driven architecture (ADR-012) is in place and events are
published and logged, but the dispatch layer from events to background workers does
not yet exist. These items must wait for the infrastructure milestone.

**Estimated sessions:** 6-10 (contingent on TaskIQ worker deployment)

**Prerequisites:**
- [ ] TaskIQ worker process deployed (Docker Compose service or process manager)
- [ ] TaskIQ broker configured (Redis-based per ADR-007)
- [ ] Task health monitoring infrastructure available
- [ ] Worker can access PostgreSQL and Redis from its runtime environment

### C1: IF-01 -- TaskIQ Task Implementation

- **ID:** IF-01
- **Layer:** Backend + Infrastructure
- **Effort:** Large (~8 hours)
- **Priority:** High (Phase 7 blocker)

**What:** Replace the two TaskIQ task stubs with real task implementations that perform
actual background work.

**How:**
1. Set up TaskIQ worker process. Options include:
   - Docker Compose service (recommended for consistency with existing setup)
   - Process manager (supervisord, systemd)
   Evaluate per deployment target (ADR-029 VM-first approach).
2. Decorate `process_feedback_memory` with `@taskiq_task`:
   - Load `FeedbackEvent` from database via repository
   - Translate feedback to memory text using existing translation logic
   - Call `mem0.add()` with user/project context for semantic preference extraction
3. Decorate `run_preference_analysis` with `@taskiq_task`:
   - Create `PreferenceAnalysisService` via dependency injection
   - Call `service.analyze(user_id, project_id)`
   - Persist analysis results
4. Add task health monitoring endpoint or metric
5. Consider splitting into separate task files per RULE-04 if the module exceeds limits

**Dependencies:** TaskIQ worker infrastructure must be deployed first.

**Files:**
- `apps/api/narrare/tasks/__init__.py` (primary change)
- Possibly new task files: `tasks/feedback_memory.py`, `tasks/preference_analysis.py` (RULE-04)
- TaskIQ broker configuration
- Docker Compose or process manager configuration

**Tests:**
- Integration test with real TaskIQ broker (in-memory broker for CI)
- Unit test: `process_feedback_memory` calls `mem0.add()` with correct arguments
- Unit test: `run_preference_analysis` creates service and calls `analyze()`
- Integration test: task health monitoring reports correct status

**RULE-XX compliance:**
- RULE-04: Split into separate files if module exceeds 300 lines
- RULE-06: Each task file has one responsibility
- RULE-07: Tasks depend on services/repositories (correct direction)
- RULE-08: TaskIQ is abstracted behind the task interface
- RULE-11: Task failures are logged and retried, not silently swallowed

**References:** ADR-007 (TaskIQ), Phase 7 milestone, INCOMPLETE-FEATURES.md IF-01

**Definition of Done:**
- [ ] TaskIQ worker process runs as a separate service
- [ ] `process_feedback_memory` calls `mem0.add()` with real data
- [ ] `run_preference_analysis` calls `PreferenceAnalysisService.analyze()`
- [ ] Task health monitoring operational
- [ ] 4 tests pass (3 unit/integration + 1 health check)
- [ ] INCOMPLETE-FEATURES.md IF-01 marked resolved

---

### C2: IF-02 -- Event Listener Dispatch

- **ID:** IF-02
- **Layer:** Infrastructure
- **Effort:** Medium (~3 hours)
- **Priority:** High (depends on IF-01)

**What:** Wire the event listener to dispatch TaskIQ tasks instead of just logging.
The `_EVENT_TASK_MAP` routing logic exists; the dispatch call is missing.

**How:**
1. In `event_listener.py`, replace the log-only handler with
   `broker.send_task(task_name, kwargs=event_data)` using the mapping in
   `_EVENT_TASK_MAP`.
2. Add error handling for dispatch failures (broker unavailable, task not registered).
3. Log successful dispatches at DEBUG level for traceability.
4. Verify that events published via `EventPublisher` reach the correct task handler.

**Dependencies:** IF-01 must be complete first (tasks must be registered with the broker).

**Files:**
- `apps/api/narrare/_app/event_listener.py` (primary change)

**Tests:**
- Integration test: publishing an event results in task enqueueing
- Integration test: event-to-task mapping routes to correct task function
- Unit test: dispatch failure is handled gracefully (logged, not raised)

**RULE-XX compliance:**
- RULE-07: Event listener depends on task layer (correct direction)
- RULE-08: Broker abstraction used, no direct Redis calls in listener
- RULE-11: Dispatch failures logged and handled, not silently swallowed

**References:** ADR-012 (Event-Driven Architecture), INCOMPLETE-FEATURES.md IF-02

**Definition of Done:**
- [ ] Log-only handler replaced with `broker.send_task()` dispatch
- [ ] `_EVENT_TASK_MAP` routing verified end-to-end
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
- [ ] No blockers (except IF-09 which waits for ANAL-002)

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

The following items cannot proceed until external prerequisites are met:

| ID | Item | Blocker | Resolution | Estimated Unblock |
|----|------|---------|------------|-------------------|
| IF-01 | TaskIQ Task Stubs | TaskIQ worker infrastructure not deployed | Phase 7 milestone: deploy worker process + broker | Phase 7 |
| IF-02 | Event Listener Dispatch | Depends on IF-01 (tasks must be registered) | Complete IF-01 first, then wire dispatch | Phase 7, after IF-01 |

**Monitoring:** These items should be re-evaluated at each phase transition. The TaskIQ
worker infrastructure is a Phase 7 milestone tracked in `docs/mvp/mvp-plan.md`.

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
| A: Quick Wins | 3 | ~3.5 hours | 2-3 | No |
| B: Feature Completion | 4 | ~14 hours | 4-6 | No |
| C: Infrastructure | 2 | ~11 hours | 6-10 | Yes |
| D: Future Enhancements | 4 | ~12 hours | Untimed | No |
| **Total** | **13** | **~40.5 hours** | **12-19+** | 2 blocked |

### By Layer

| Layer | Items | IDs |
|-------|-------|-----|
| Backend | 5 | IF-01, IF-02, IF-03, IF-04, IF-08 |
| Core | 4 | IF-06, IF-09, IF-10, IF-11 |
| Core + Backend | 1 | IF-05 |
| Full-stack | 1 | IF-12 |
| Documentation | 1 | IF-13 |
| Architecture Decision | 1 | IF-07 |

### By Effort

| Effort | Count | IDs |
|--------|-------|-----|
| Small (<2 hours) | 4 | IF-03, IF-08, IF-07, IF-09 |
| Medium (2-4 hours) | 5 | IF-04, IF-05, IF-06, IF-10, IF-12, IF-13 |
| Large (4+ hours) | 3 | IF-01, IF-02, IF-11 |

### Resolution Priority (Recommended Execution Order)

Within each wave, items are ordered by priority and dependency:

| Order | ID | Wave | Rationale |
|-------|----|------|-----------|
| 1 | IF-03 | A | Smallest effort, closes ADR-023 gap |
| 2 | IF-08 | A | Trivial fix, reduces placeholder debt |
| 3 | IF-04 | A | Medium effort, improves search quality |
| 4 | IF-05 | B | Needs Alembic migration -- do early in wave |
| 5 | IF-06 | B | Depends on protocol pattern -- follows IF-05 |
| 6 | IF-12 | B | Full-stack -- allocate dedicated session |
| 7 | IF-13 | B | Documentation -- can overlap with other work |
| 8 | IF-01 | C | Blocked -- begins when TaskIQ worker deployed |
| 9 | IF-02 | C | Blocked -- begins after IF-01 complete |
| 10-13 | IF-09, IF-10, IF-11, IF-07 | D | Opportunistic -- no fixed order |

---

## Cross-Reference

This plan is derived from and must be kept in sync with:

| Document | Relationship |
|----------|-------------|
| `docs/architecture/INCOMPLETE-FEATURES.md` | Source inventory -- IF-01 through IF-13 |
| `docs/_shared/CURRENT_STATE.md` | Project phase and status |
| `docs/_shared/CONSTRAINTS.md` | RULE-XX compliance requirements |
| `docs/mvp/mvp-plan.md` | Phase 7 milestone (TaskIQ worker) |
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
3. When the TaskIQ worker infrastructure is deployed -- re-evaluate Wave C estimates.
4. At each phase transition -- review all remaining items for priority changes.

---

> **Last reviewed:** 2026-06-10
> **Next review:** After Wave A completion or Phase 7 planning, whichever comes first
