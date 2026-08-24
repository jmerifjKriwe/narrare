---
id: INCOMPLETE-FEATURES
title: "Incomplete Features, Stubs, and TODO Markers"
status: active
area: architecture
mvp: false
date_created: 2026-06-10
last_updated: 2026-08-08
---

# Incomplete Features, Stubs, and TODO Markers

> **Purpose:** Catalogue all known incomplete features, stubs, placeholders, and TODO
> markers in the Narrare codebase. This document serves as a prioritized inventory for
> planning and tracking. It is NOT a changelog -- it tracks technical debt and future work.

---

## Summary Table

| ID | Priority | Area | Description | Status | Blocking |
|----|----------|------|-------------|--------|----------|
| ~~IF-01~~ | ~~High~~ | ~~Tasks / Memory~~ | ~~TaskIQ task stubs (`process_feedback_memory`, `run_preference_analysis`) — tasks registered with `@broker.task` and retries, but bodies only log~~ | **SUPERSEDED** | ~~Superseded 2026-08-07 by ADR-080 — broker + stubs removed~~ |
| ~~IF-02~~ | ~~High~~ | ~~Events / Embeddings~~ | ~~Event listener `_dispatch` code exists but `_EVENT_TASK_MAP` is empty, listener is not wired into lifespan~~ | **SUPERSEDED** | ~~Superseded 2026-08-07 by ADR-080 — EventListener + event bus removed~~ |
| ~~IF-03~~ | ~~High~~ | ~~Settings / Writing~~ | ~~Co-author word limit uses hardcoded default~~ | **RESOLVED** | ~~Resolved 2026-06-10~~ |
| ~~IF-04~~ | ~~Medium~~ | ~~Embeddings / Search~~ | ~~`ScoredCandidate` missing metadata~~ | **RESOLVED** | ~~Resolved 2026-06-10~~ |
| ~~IF-05~~ | ~~Medium~~ | ~~KB / Provenance~~ | ~~Auto-extracted KB entries lack origin metadata~~ | **RESOLVED** | ~~Resolved 2026-06-10~~ |
| ~~IF-06~~ | ~~Medium~~ | ~~KB / AI Invocation~~ | ~~KB suggested context uses placeholder text~~ | **RESOLVED** | ~~Resolved 2026-06-10~~ |
| IF-07 | Medium | Wiki / Core | Core-layer `get_summaries()` returns empty dict | **Open** | No |
| ~~IF-08~~ | ~~Medium~~ | ~~Chat / API~~ | ~~Chat history response uses `UUID(int=0)` placeholder~~ | **RESOLVED** | ~~Resolved 2026-06-10~~ |
| IF-09 | Low | Analysis / Types | Narrative arc segments untyped (`list[dict]`) | **Open** | No |
| IF-10 | Low | NLP / Emotions | Full NRC EmoLex loader raises `NotImplementedError` | **Open** | No |
| IF-11 | Low | Memory / Embeddings | Embedding cascade Tier 2 (provider-native) not implemented | **Open** | No |
| ~~IF-12~~ | ~~Low~~ | ~~Generation / Frontend~~ | ~~Name generator save-to-KB button is a console log~~ | **RESOLVED** | ~~Resolved 2026-06-10~~ |
| ~~IF-13~~ | ~~Doc~~ | ~~Feature Specs~~ | ~~4 feature specs with `n:` placeholder markers (36 total)~~ | **RESOLVED** | ~~Resolved 2026-06-10~~ |

---

## Resolved Items

> Items resolved during Wave A + B remediation (2026-06-10) and INFRA-007 (2026-06-29).
> Kept for audit trail.

### ~~IF-03: Settings Cascade -- Hardcoded Default~~ (RESOLVED 2026-06-10)

- **Resolution:** Added `max_selection_words` to `TokenLimitOverrides` dataclass, wired through
  SET-005 cascade into `CoAuthorService`. Replaced hardcoded `max_words = 2000` with cascade
  resolution (user → project → default 2000). 9 tests.
- **Files:** `settings/token_limits/contracts.py`, `settings/token_limits/service.py`,
  `settings/token_limits/schemas.py`, `_app/config.py`, `writing/coauthor_service.py`,
  `writing/deps.py`

### ~~IF-04: Embedding Service -- Missing Metadata Wire-Up~~ (RESOLVED 2026-06-10)

- **Resolution:** Extended search query to LEFT JOIN `kb_entries`, bringing `usage_count` and
  `last_referenced_at` into `ScoredCandidate`. Introduced `SearchRow` dataclass for typed
  results. 7 tests.
- **Files:** `embeddings/search_queries.py`, `embeddings/contracts.py`,
  `embeddings/repository.py`, `embeddings/service.py`

### ~~IF-05: KB Extraction -- Missing Provenance~~ (RESOLVED 2026-06-10)

- **Resolution:** Added `source` and `review_status` fields to `KBEntryCreate` schema and
  `KBEntry` model. Extraction sets `source="auto_extraction"`, `review_status="pending"`.
  Added `review_status` filter to KB listing. Alembic migration 0029. 10 tests.
- **Files:** `kb/schemas.py`, `kb/models.py`, `kb/contracts.py`, `kb/repository.py`,
  `kb/service.py`, `kb/router.py`, `kb/extraction_apply_service.py`,
  new migration `0029_kb_provenance.py`

### ~~IF-06: KB Suggested Context -- Placeholder Text~~ (RESOLVED 2026-06-10)

- **Resolution:** Replaced `_PLACEHOLDER_TEXT` with graceful degradation -- enrichment skipped
  (with debug log) when no provider configured. Placeholder string completely removed. 7 tests.
- **Files:** `core/ai_invocation/enrichers/kb_suggested.py`

### ~~IF-08: Chat Router -- Placeholder Project ID~~ (RESOLVED 2026-06-10)

- **Resolution:** Added `get_conversation_project_id()` to `ConversationStore` ABC and
  `ChatServiceProtocol`. Router now loads real `project_id` from conversation. Explicit
  fallback to `UUID(int=0)` when conversation has no project. 4 tests.
- **Files:** `core/chat/conversation_store.py`, `core/chat/contracts.py`,
  `chat/conversation_store.py`, `chat/chat_service.py`, `chat/router.py`
- **Note (2026-08-21):** The `UUID(int=0)` fallback described above is itself superseded
  by NOTES-001 -- `project_id` is now honestly nullable/null (migration `0042`), see
  `docs/features/notes/NOTES-001-scratchpad.md`.

### ~~IF-12: Name Generator -- KB Save Not Implemented (Frontend)~~ (RESOLVED 2026-06-10)

- **Resolution:** Replaced `console.log` stub with real `kbApi.createEntry` call. Added
  per-name save state tracking (idle/saving/saved/error) with visual feedback. Reused
  existing KB create endpoint with `source="name_generator"`. i18n keys in 3 locales.
  6 tests.
- **Files:** `NameResults.tsx`, `NameGenerator.tsx`, `lib/api/kb.ts`,
  i18n files (en/de/fr)

### ~~IF-13: Doc Placeholders -- Feature Spec `n:` Markers~~ (RESOLVED 2026-06-10)

- **Resolution:** All 36 `n:` placeholders filled across 4 feature specs with real content
  (tooltips, help texts, descriptions, implementation details, limitations, related
  features).
- **Files:** `SETUP-003-import.md`, `IO-001-export.md`, `IO-002-import.md`,
  `IO-003-sync.md`

---

## Section 1: High Priority -- Blocking Stubs with Defined Interfaces

### IF-01: TaskIQ Task Stubs (Task Logic Not Implemented)

> **⛔ SUPERSEDED BY ADR-080 (2026-08-07).** This item is **no longer open**.
> ADR-080 (Remove Redis & TaskIQ for Single-User Deployment) deleted the TaskIQ
> broker (`tasks/broker.py`), the worker process, and the broker-registered task
> stubs. `apps/api/narrare/tasks/__init__.py` was reduced to an ~18-line
> docstring with **no `@broker.task` stubs and no broker**, then **deleted**
> entirely in the ADR-080 CI cleanup (nothing imported it — commit `e45905fb`,
> 2026-08-08). The line ranges, decorator claims, and "infrastructure complete
> via INFRA-007" premise below describe the **pre-ADR-080** state and are
> retained only as an audit trail. The two named
> tasks (`process_feedback_memory`, `run_preference_analysis`) were Phase-7 stubs
> that were **never wired**; per ADR-080 they are removed rather than
> implemented. Background work that *does* run now uses in-process
> `asyncio.create_task` (see INFRA-007 / ADR-080). See
> [ADR-080](decisions/ADR-080-remove-redis-taskiq-in-process-execution.md).

The following is the historical (pre-ADR-080) record:

- **File:** `apps/api/narrare/tasks/__init__.py` *(phantom as described —
  reduced to an ~18-line docstring by ADR-080, then **deleted** entirely in the
  CI cleanup: nothing imported it (commit `e45905fb`, 2026-08-08); the stubs
  and lines 36–81 no longer exist)*
- **Marker:** `# TODO (Phase 7)` at lines 54 and 78; `status="stub"` in log calls
- **Description:** Two async task functions are decorated with `@broker.task` (TaskIQ),
  have `max_retries=3`, and accept typed events — but their bodies only log and skip
  actual work:
  1. `process_feedback_memory` — Must load `FeedbackEvent` from DB, translate to memory
     text, and call `mem0.add()`.
  2. `run_preference_analysis` — Must create `PreferenceAnalysisService` with DI and call
     `service.analyze()`.
- **Infrastructure status:** TaskIQ broker + worker are deployed via Docker Compose
  as part of INFRA-007 (2026-06-29). Redis transport + result backend, monitoring API,
  and Docker worker service all exist. The blocker is no longer infrastructure — it is
  the **task logic implementation**.
- **Blocker:** Task logic not implemented — neither function calls `mem0.add()` nor
  `PreferenceAnalysisService.analyze()`. Requires DI access to repos/services and a
  `mem0` client instance.
- **Affects:** Memory/learning pipeline, preference extraction.
- **References:** ADR-007 (TaskIQ), INFRA-007 (Background Tasks deployed), Phase 7
  milestone (task logic).

### IF-02: Event Listener -- Empty Event Map + Inactive Listener

> **⛔ SUPERSEDED BY ADR-080 (2026-08-07).** This item is **no longer open**.
> ADR-080 deleted the dormant `EventListener` class together with the Redis
> Pub/Sub event bus it depended on, so the `_EVENT_TASK_MAP` / `broker.kiq()`
> dispatch path no longer exists. The referenced file
> `apps/api/narrare/_app/event_listener.py` is a **phantom — it has been
> deleted**. The "INFRA-007 broker + worker exist" premise below describes the
> **pre-ADR-080** state only. See
> [ADR-080](decisions/ADR-080-remove-redis-taskiq-in-process-execution.md)
> (supersedes ADR-007 / ADR-012).

The following is the historical (pre-ADR-080) record:

- **File:** `apps/api/narrare/_app/event_listener.py` *(phantom — file deleted
  by ADR-080; the listener, `_EVENT_TASK_MAP`, and `broker.kiq()` dispatch no
  longer exist)*
- **Lines:** 35--38 (event map), 99--107 (start method)
- **Marker:** `# pending: no registered chapter-embedding task` and `# pending: no registered cleanup task` — commented-out map entries
- **Description:** The `_EVENT_TASK_MAP` is empty (only commented-out entries). The
  `EventListener` class is fully implemented with `_dispatch()` that can enqueue via
  `broker.kiq()`, but:
  1. No event types are mapped to task names in `_EVENT_TASK_MAP`
  2. The listener is not wired into the application lifespan (`_app/lifespan.py`)
- **Infrastructure note:** Since INFRA-007 (2026-06-29), the TaskIQ broker + worker
  exist and tasks like `process_feedback_memory` and `run_preference_analysis` are
  registered (though stubs). The listener could dispatch to these if the map were
  populated and the listener activated.
- **Blocker:** (a) Depends on IF-01 being implemented first (tasks must have real
  logic before they are dispatched); (b) event-to-task mapping must be populated;
  (c) listener must be wired into the application lifespan.
- **Affects:** Embedding updates on content change, KB entry re-indexing, wiki
  stale-marking, feedback memory processing.
- **References:** ADR-012 (Event-Driven Architecture), INFRA-007 (Background Tasks).

---

## Section 2: Medium Priority -- Feature Gaps

### IF-07: Wiki Summaries -- Core Layer Stub

- **File:** `packages/core/narrare_core/wiki/service.py`
- **Lines:** 120--139
- **Marker:** `Phase 1 (core): Stub -- returns empty dict.`
- **Description:** `get_summaries()` returns an empty dict at the core layer. Real lookup
  happens in the API layer via `WikiRepository`. The core-layer stub is intentional (core
  has no DB access) but limits testability of core-level consumers that need wiki data.
- **Affects:** Core-level wiki summary access -- unit tests must mock or skip wiki
  enrichment.
- **References:** ADR-022 (LLM Wiki), WIKI-001.

---

## Section 3: Lower Priority -- Future Enhancements

### IF-09: Narrative Arc Detection -- Untyped Segments (ANAL-002)

- **File:** `packages/core/narrare_core/analysis/types.py`
- **Line:** 251
- **Marker:** `# TODO(ANAL-002): Replace with a typed segment model once arc detection is implemented.`
- **Description:** `NarrativeArc.segments` uses `list[dict[str, object]]` instead of a
  typed model. The arc detection algorithm is not yet implemented -- the type is a
  forward-looking placeholder.
- **Affects:** Sentiment analysis arc quality -- consumers must handle untyped dicts.
- **References:** ANAL-002.

### IF-10: NRC EmoLex -- NotImplementedError

- **File:** `packages/core/narrare_core/nlp/languages/emotions/__init__.py`
- **Line:** 181
- **Marker:** `raise NotImplementedError("Full NRC EmoLex loading is not yet implemented.")`
- **Description:** The full NRC Emotion Lexicon loading function exists but throws
  `NotImplementedError`. Only a built-in subset is available via `get_emotions()`. Full
  EmoLex support would improve emotion analysis accuracy, especially for non-English
  languages.
- **Affects:** Emotion analysis accuracy for non-English languages.
- **References:** ANAL-002.

### IF-11: Embedding Cascade -- Tier 2 Not Implemented

- **File:** `packages/core/narrare_core/memory/embedding_cascade.py`
- **Line:** 4
- **Marker:** `Tier 2: Provider-native embeddings (future hook, not implemented now)`
- **Description:** The 4-tier embedding cascade has Tier 2 (provider-native embeddings)
  as a future hook. Current flow skips Tier 2: Tier 1 (OpenAI) -> Tier 3 (local) -> Tier 4
  (disabled). Tier 2 would use Anthropic or Google embedding APIs when the user has those
  keys configured.
- **Affects:** Embedding optimization for users with Anthropic/Google API keys -- they
  fall back to local embeddings instead of using provider-native ones.
- **References:** ADR-017 (superseded by ADR-033), ADR-033 (mem0 v3).

---

## Statistics

### Overall Progress

| Metric | Count |
|--------|-------|
| **Total items** | **13** |
| **Resolved** | **7** (IF-03, IF-04, IF-05, IF-06, IF-08, IF-12, IF-13) |
| **Superseded** | **2** (IF-01, IF-02 — superseded by ADR-080, 2026-08-07) |
| **Remaining** | **4** (IF-07, IF-09, IF-10, IF-11) |

### By Priority (Remaining Only)

| Priority | Resolved | Superseded | Remaining | Remaining IDs |
|----------|----------|-----------|-----------|---------------|
| High | 1 (IF-03) | 2 (IF-01, IF-02) | 0 | — |
| Medium | 4 (IF-04, IF-05, IF-06, IF-08) | 0 | 1 | IF-07 |
| Low | 1 (IF-12) | 0 | 3 | IF-09, IF-10, IF-11 |
| Documentation | 1 (IF-13) | 0 | 0 | — |

### By Area (Remaining Only)

| Area | Remaining | IDs |
|------|-----------|-----|
| Wiki | 1 | IF-07 |
| Analysis / NLP | 2 | IF-09, IF-10 |
| Memory / Embeddings | 1 | IF-11 |

### By Marker Type (Remaining Only)

| Marker Type | Count |
|------------|-------|
| `NotImplementedError` | 1 |
| Stub comment | 1 |
| `TODO` (unqualified) | 1 |
| Future hook comment | 1 |
| **Total remaining** | **4** |

### Blocking Status (Remaining Only)

| Status | Count |
|--------|-------|
| Non-blocking (quality gap) | 4 |

---

## Maintenance

This document should be updated:

1. When a TODO/stub is resolved -- move to the "Resolved Items" section with the resolution
   date and summary, update the summary table and statistics.
2. When a new TODO/stub is discovered during code review -- add an entry following the
   same format.
3. At each phase transition -- review all entries for relevance and priority changes.
4. ~~When IF-01 is resolved (task logic implemented) -- update IF-02 blocking status and
   re-evaluate priority.~~ *(Moot — IF-01 and IF-02 were superseded by ADR-080 on
   2026-08-07: the TaskIQ broker, worker, task stubs, and dormant EventListener
   were removed in favour of in-process `asyncio.create_task`.)*

---

> **Last reviewed:** 2026-08-08 (IF-01/IF-02 reclassified as superseded by ADR-080)
> **Next review:** Before Phase 7 planning, or when a future ADR re-introduces a broker
