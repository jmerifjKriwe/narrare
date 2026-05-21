## 1. Core: Embedding Cascade

- [x] 1.1 Create `core/memory/embedding_cascade.py` with `EmbeddingCascadeResolver` that resolves embedding config from user providers (Stufe 1-4: OpenAI → provider-native → sentence-transformers → disabled)
- [x] 1.2 Define `EmbeddingConfig` dataclass (provider, model, api_key?, base_url?) in `core/memory/embedding_cascade.py`
- [x] 1.3 Write unit tests for all cascade scenarios (OpenAI user, z.ai user, Anthropic user, Ollama user, multi-provider user)
- [x] 1.4 Add `sentence-transformers` as optional dependency in `pyproject.toml`

## 2. Core: FeedbackEvent Extension

- [x] 2.1 Add optional `rating: int | None` field to `FeedbackEvent` in `core/memory/models.py`
- [x] 2.2 Update `FeedbackService._translate_to_memory_text()` to include rating and enriched context (chapter, genre, mode) in the memory text
- [x] 2.3 Write unit tests for updated translation (accept with rating, reject with reason, modify with diff)

## 3. Core: mem0 Client Rewrite

- [x] 3.1 Rewrite `core/memory/mem0_client.py` — `create_memory_client()` now takes user settings, uses embedding cascade resolver, includes custom extraction instructions for writing preferences
- [x] 3.2 Define `WRITING_PREFERENCE_EXTRACTION_PROMPT` custom instructions for mem0 (German/English, writing-domain-specific extraction)
- [x] 3.3 Implement `MemoryClientCache` — bounded LRU cache for AsyncMemory instances per user_id, with invalidation on settings change
- [x] 3.4 Write unit tests for client creation with different provider configs (z.ai + local embeddings, OpenAI + OpenAI embeddings, Anthropic + local embeddings)

## 4. Core: PreferenceAnalysisAgent

- [x] 4.1 Create `core/agents/preference_analysis_types.py` — `PreferenceAnalysisOutput` (style_patterns, content_patterns, avoidance_patterns, confidence, summary) and `PreferenceAnalysisDeps` (language, genre, event_count)
- [x] 4.2 Create `core/agents/preference_analysis_agent.py` — `PreferenceAnalysisAgent(NarrareAgent)` with system prompt for writing preference analysis
- [x] 4.3 Export from `core/agents/__init__.py`
- [x] 4.4 Write agent-level unit tests using TestModel

## 5. Backend: Migrations

- [x] 5.1 Create Alembic migration adding `rating` column (INTEGER nullable, CHECK 1-5) to `feedback_events` table
- [x] 5.2 Create Alembic migration adding `embedding_provider` (VARCHAR default "auto") and `embedding_model` (VARCHAR nullable) to `user_ai_settings` table
- [x] 5.3 Create Alembic migration for `preference_profiles` table (id, user_id, project_id, style_patterns JSONB, content_patterns JSONB, avoidance_patterns JSONB, confidence float, summary text, event_count_at_analysis int, created_at, updated_at, UNIQUE on user_id+project_id)

## 6. Backend: Memory Module Updates

- [x] 6.1 Update `memory/schemas.py` — add `rating` (Optional[int]) and enriched context fields to `FeedbackRequest`
- [x] 6.2 Update `memory/service.py` — `MemoryFeedbackService.record_feedback()` now includes rating, publishes `FeedbackRecorded` event instead of direct mem0 call
- [x] 6.3 Create `memory/analysis_service.py` — `PreferenceAnalysisService` that orchestrates PreferenceAnalysisAgent, persists to preference_profiles table
- [x] 6.4 Update `memory/repository.py` — add `get_event_count(user_id, project_id)`, `get_events_batch(user_id, project_id, limit)` for agent input
- [x] 6.5 Rewrite `memory/router.py` DI factories — use real AsyncMemory via MemoryClientCache, inject embedding cascade resolver
- [x] 6.6 Add `POST /memory/analyze` endpoint in router, with minimum event count guard (5 events)
- [x] 6.7 Write integration tests for all memory endpoints with FakeMemoryClient

## 7. Backend: Event-Driven mem0 Processing

- [x] 7.1 Define `FeedbackRecorded` event in core/events/ with user_id, project_id, event_id fields
- [x] 7.2 Define `PreferenceAnalysisTriggered` event (emitted at thresholds 20, 50, 100, 200...)
- [x] 7.3 Create TaskIQ task `process_feedback_memory` — receives FeedbackRecorded event, calls mem0.add()
- [x] 7.4 Create TaskIQ task `run_preference_analysis` — receives PreferenceAnalysisTriggered event, runs PreferenceAnalysisAgent
- [x] 7.5 Register both tasks in event_listener.py routing
- [x] 7.6 Write unit tests for event publishing and task logic

## 8. Backend: Settings Integration

- [x] 8.1 Add `embedding_provider` and `embedding_model` to user AI settings schemas (request/response)
- [x] 8.2 Add `active_embedding_tier` computed field to GET response (which cascade level is in use)
- [x] 8.3 Update `user_ai_settings` repository for new fields
- [x] 8.4 Write unit tests for settings update with embedding config

## 9. Frontend: Modify-Tracking & Rating

- [x] 9.1 Update `GenerationDraft.tsx` — track original vs. edited text, send action="modify" with diff when text was edited before accept
- [x] 9.2 Create `components/studio/editor/RatingPrompt.tsx` — inline 1-5 star rating after accept/reject, optional rejection reason textarea
- [x] 9.3 Create `lib/api/memory.ts` — `memoryApi` client (recordFeedback, getPreferences, resetPreferences, triggerAnalysis)
- [x] 9.4 Create `lib/hooks/useMemory.ts` — TanStack Query hooks (usePreferences, useMemoryStatus, useRecordFeedback)
- [x] 9.5 Write component tests for modify-tracking and rating UI

## 10. Frontend: Preference Profile Page

- [x] 10.1 Create `components/settings/LearningTab.tsx` — preference profile display with style/content/constraints sections, confidence, event count, project selector, reset button
- [x] 10.2 Create `components/settings/PreferenceProfile.tsx` — read-only preference display component (style list, content list, avoidance patterns)
- [x] 10.3 Create `components/settings/LearningStatus.tsx` — progress indicator ("X/50 interactions") with tooltip
- [x] 10.4 Integrate LearningTab into Settings page
- [x] 10.5 Add i18n keys for all feedback loop UI text in en, de, fr locales (studio + settings namespaces)
- [x] 10.6 Write component tests for preference profile page

## 11. Frontend: Integration

- [x] 11.1 Wire GenerationPanel to show RatingPrompt after accept/reject
- [x] 11.2 Wire LearningStatus into GenerationPanel or MetadataSidebar
- [x] 11.3 Update WritingService accept/reject flows to include enriched context (chapter_id, genre, mode)
- [x] 11.4 End-to-end smoke test: generate → accept with rating → verify feedback recorded → verify preference profile updated

## 12. Documentation

- [x] 12.1 Update LEARN-001 feature spec (status → implemented)
- [x] 12.2 Update INFRA-005 feature spec (status → implemented)
- [x] 12.3 Create ADR for embedding cascade decision
- [x] 12.4 Update TECH_STACK.md — mem0 embedding strategy, sentence-transformers entry
- [x] 12.5 Update CURRENT_STATE.md with LEARN-001 implementation details
