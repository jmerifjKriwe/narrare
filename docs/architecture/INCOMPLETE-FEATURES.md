---
id: INCOMPLETE-FEATURES
title: "Incomplete Features, Stubs, and TODO Markers"
status: active
area: architecture
mvp: false
date_created: 2026-06-10
last_updated: 2026-06-10
---

# Incomplete Features, Stubs, and TODO Markers

> **Purpose:** Catalogue all known incomplete features, stubs, placeholders, and TODO
> markers in the Narrare codebase. This document serves as a prioritized inventory for
> planning and tracking. It is NOT a changelog -- it tracks technical debt and future work.

---

## Summary Table

| ID | Priority | Area | Description | Blocking |
|----|----------|------|-------------|----------|
| IF-01 | High | Tasks / Memory | TaskIQ task stubs (`process_feedback_memory`, `run_preference_analysis`) | Yes -- Phase 7 |
| IF-02 | High | Events / Embeddings | Event listener logs but does not dispatch tasks | Yes -- depends on IF-01 |
| IF-03 | High | Settings / Writing | Co-author word limit uses hardcoded default instead of SET-005 cascade | Partial -- ADR-023 gap |
| IF-04 | Medium | Embeddings / Search | `ScoredCandidate` missing `usage_count` and `last_referenced_at` metadata | No |
| IF-05 | Medium | KB / Provenance | Auto-extracted KB entries lack origin metadata | No |
| IF-06 | Medium | KB / AI Invocation | KB suggested context uses placeholder text | No |
| IF-07 | Medium | Wiki / Core | Core-layer `get_summaries()` returns empty dict | No |
| IF-08 | Medium | Chat / API | Chat history response uses `UUID(int=0)` placeholder | No |
| IF-09 | Low | Analysis / Types | Narrative arc segments untyped (`list[dict]`) | No |
| IF-10 | Low | NLP / Emotions | Full NRC EmoLex loader raises `NotImplementedError` | No |
| IF-11 | Low | Memory / Embeddings | Embedding cascade Tier 2 (provider-native) not implemented | No |
| IF-12 | Low | Generation / Frontend | Name generator save-to-KB button is a console log | No |
| IF-13 | Doc | Feature Specs | 4 feature specs with `n:` placeholder markers (36 total) | No |

---

## Section 1: High Priority -- Blocking Stubs with Defined Interfaces

### IF-01: TaskIQ Task Stubs (Phase 7 Dependency)

- **File:** `apps/api/narrare/tasks/__init__.py`
- **Lines:** 23--46, 49--72
- **Marker:** `# TODO (Phase 7)` at lines 43 and 69
- **Description:** Two async task functions are stubs that only log events rather than
  performing actual work:
  1. `process_feedback_memory` -- Must load `FeedbackEvent` from DB, translate to memory
     text, and call `mem0.add()`.
  2. `run_preference_analysis` -- Must create `PreferenceAnalysisService` with DI and call
     `service.analyze()`.
- **Blocker:** TaskIQ worker integration not yet complete.
- **Affects:** Memory/learning pipeline, preference extraction.
- **References:** ADR-007 (TaskIQ), Phase 7 milestone.

### IF-02: Event Listener -- No Task Dispatch (Phase 5+)

- **File:** `apps/api/narrare/_app/event_listener.py`
- **Line:** 22
- **Marker:** `# Tasks will be implemented in Phase 5+ -- for now we log the routing.`
- **Description:** The event-to-task mapping exists in `_EVENT_TASK_MAP` but events are
  only logged, not dispatched to TaskIQ workers. The routing logic is in place; the
  dispatch call is missing.
- **Blocker:** Depends on IF-01 (TaskIQ integration).
- **Affects:** Embedding updates on content change, KB entry re-indexing, wiki stale-marking.
- **References:** ADR-012 (Event-Driven Architecture).

### IF-03: Settings Cascade -- Hardcoded Default

- **File:** `apps/api/narrare/writing/coauthor_service.py`
- **Lines:** 113--117
- **Marker:** `# TODO: Resolve from UserSettings/ProjectSettings when a generic settings cascade infrastructure exists.`
- **Description:** The co-author word limit uses a hardcoded `max_words = 2000` instead
  of resolving from the SET-005 settings cascade (user -> project -> default). The SET-005
  infrastructure exists for other endpoints but the generic cascade resolver is not yet
  wired into the co-author service.
- **Blocker:** Requires generic settings cascade infrastructure.
- **Affects:** Co-author validation accuracy -- all users share the same limit regardless
  of preferences.
- **References:** ADR-023 (Co-Author Change Engine), SET-005.

---

## Section 2: Medium Priority -- Feature Gaps

### IF-04: Embedding Service -- Missing Metadata Wire-Up

- **File:** `apps/api/narrare/embeddings/service.py`
- **Lines:** 166--167
- **Marker:** `# TODO: wire up usage_count from kb_entries`, `# TODO: wire up last_referenced_at from kb_entries`
- **Description:** `ScoredCandidate` always has `usage_count=0` and `last_referenced_at=None`.
  The hybrid scoring algorithm cannot use recency or usage frequency signals for ranking
  because the data is not wired from the KB entries table.
- **Affects:** Search result ranking quality -- candidates are scored on semantic similarity
  alone, without recency or usage boosts.
- **References:** INFRA-004 (Embedding Store), KB-005 (Proactive Context).

### IF-05: KB Extraction -- Missing Provenance

- **File:** `apps/api/narrare/kb/extraction_apply_service.py`
- **Lines:** 172--174
- **Marker:** `# TODO(CR-AUFG-04-B3): Once KBEntryCreate supports provenance fields...`
- **Description:** Auto-extracted KB entries do not carry origin metadata. The
  `KBEntryCreate` schema lacks provenance fields (`source="auto_extraction"`,
  `review_status="pending"`). Without these, extracted entries are indistinguishable
  from manually created ones.
- **Affects:** KB entry provenance tracking, review workflow, extraction quality metrics.
- **References:** CR-AUFG-04-B3, KB-007 (Extraction).

### IF-06: KB Suggested Context -- Placeholder Text

- **File:** `packages/core/narrare_core/ai_invocation/enrichers/kb_suggested.py`
- **Line:** 36
- **Marker:** `_PLACEHOLDER_TEXT: str = "[KB context will be provided in a future update]"`
- **Description:** When no KB provider is configured, a placeholder string is injected
  into prompts instead of real KB context. The `KBSuggestedProvider` protocol exists but
  no real implementation wires it. All AI invocations that depend on KB context receive
  the placeholder.
- **Affects:** AI invocation quality without KB context -- prompts contain a visible
  placeholder marker.
- **References:** CR-03 (AI Invocation), INFRA-013.

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

### IF-08: Chat Router -- Placeholder Project ID

- **File:** `apps/api/narrare/chat/router.py`
- **Line:** 99
- **Marker:** `project_id=UUID(int=0),  # placeholder -- will be enriched in future`
- **Description:** Chat history response uses `UUID(int=0)` as a project_id placeholder.
  The real project context should come from the conversation's associated project but
  the wire-up is not implemented.
- **Affects:** Chat history project association -- frontend cannot link chat sessions to
  projects.
- **References:** CHAT-001, ADR-024 (Free-Form Chat).

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

### IF-12: Name Generator -- KB Save Not Implemented (Frontend)

- **File:** `packages/web/components/studio/generation/NameResults.tsx`
- **Line:** 37
- **Marker:** `// TODO: Implement KB save when API is available`
- **Description:** Generated name results have a save-to-KB button that only logs to
  console. No API endpoint or frontend integration exists to persist generated names as
  KB entries.
- **Affects:** Name generator -> KB workflow -- users cannot save generated names to their
  knowledge base.
- **References:** GEN-001.

---

## Section 4: Documentation Gaps (Feature Spec Placeholders)

These feature specs contain `n:` markers indicating incomplete documentation. These are
NOT code issues but represent feature specs that still need content for the Documentation
Gate.

| Feature Spec | `n:` Count | Status |
|-------------|-----------|--------|
| `SETUP-003-import.md` | 9 | Missing: tooltip, help text, description, implementation details, limitations, related features |
| `IO-001-export.md` | 9 | Missing: tooltip, help text, description, implementation details, limitations, related features |
| `IO-002-import.md` | 9 | Missing: tooltip, help text, description, implementation details, limitations, related features |
| `IO-003-sync.md` | 9 | Missing: tooltip, help text, description, implementation details, limitations, related features |

**Total `n:` markers:** 36 across 4 feature specs.

These must be resolved before the affected features can pass the Documentation Gate and
reach status:stable.

---

## Statistics

### By Priority

| Priority | Count |
|----------|-------|
| High | 3 |
| Medium | 5 |
| Low | 4 |
| Documentation | 1 (covering 4 specs) |
| **Total** | **13** |

### By Area

| Area | Count | IDs |
|------|-------|-----|
| Tasks / Memory / Events | 2 | IF-01, IF-02 |
| Writing / Settings | 1 | IF-03 |
| Embeddings / Search | 2 | IF-04, IF-11 |
| Knowledge Base | 2 | IF-05, IF-06 |
| Wiki | 1 | IF-07 |
| Chat | 1 | IF-08 |
| Analysis / NLP | 2 | IF-09, IF-10 |
| Generation / Frontend | 1 | IF-12 |
| Documentation / Specs | 1 | IF-13 |

### By Marker Type

| Marker Type | Count |
|------------|-------|
| `TODO (Phase N)` | 2 |
| `TODO` (unqualified) | 6 |
| `NotImplementedError` | 1 |
| Placeholder text/string | 2 |
| Stub comment | 1 |
| `n:` doc marker (36 instances) | 1 grouped |
| **Total** | **13** |

### Blocking Status

| Status | Count |
|--------|-------|
| Blocking (depends on external infrastructure) | 2 |
| Partial gap (works but incomplete) | 1 |
| Non-blocking (quality gap) | 9 |
| Documentation only | 1 |

---

## Maintenance

This document should be updated:

1. When a TODO/stub is resolved -- move to a "Resolved" section with the resolution date
   and PR reference, or remove if the list grows too long.
2. When a new TODO/stub is discovered during code review -- add an entry following the
   same format.
3. At each phase transition -- review all entries for relevance and priority changes.

---

> **Last reviewed:** 2026-06-10
> **Next review:** Before Phase 7 planning
