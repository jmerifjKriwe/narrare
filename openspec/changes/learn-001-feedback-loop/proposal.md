## Why

The feedback loop is a foundational prerequisite for LEARN-002 (Style Adaptation), WRITE-006 (Co-author), and ANAL-007 (Voice Analysis). Without it, every AI suggestion is generic — no adaptation to the writer's voice, no avoidance of rejected patterns, no personalization over time. The memory layer infrastructure (INFRA-005) exists as stubs and protocols, but the actual loop is broken: the router creates `NullMemoryClient` instead of a real mem0 client, so preferences are always empty. This change closes the loop: feedback is recorded, preferences are extracted via mem0 with LLM-powered fact extraction, and preferences are injected into prompts for better suggestions. Critically, the system must work for users who only have a single provider — including z.ai and Anthropic, which do not offer embedding APIs. A 4-tier embedding cascade (OpenAI → provider-native → local sentence-transformers → disabled) ensures graceful degradation at every level.

## What Changes

- **Wire up mem0 AsyncMemory** in the backend memory router, replacing `NullMemoryClient` with a real client configured from user's provider settings
- **Embedding cascade resolver** — new resolution logic that selects the best available embedding source: (1) OpenAI text-embedding-3-small if user has OpenAI key, (2) provider-native embeddings if available, (3) local sentence-transformers (all-MiniLM-L6-v2, no API key), (4) NullMemoryClient (memory disabled)
- **Embedding configuration in SET-003** — add `embedding_provider` ("auto" | "openai" | "local" | "disabled") and `embedding_model` fields to `user_ai_settings`, with auto-cascade as default
- **Rating field** — add optional `rating` (1-5) to `FeedbackEvent`, `FeedbackRequest` schema, and `feedback_events` migration
- **Rich feedback context** — WritingService and session handlers enrich feedback events with chapter_id, genre, mode, and project context
- **Async mem0 processing** — mem0.add() calls run via TaskIQ background tasks (ADR-012 event-driven), not blocking the HTTP response
- **Custom extraction instructions** — mem0 configured with writing-domain-specific `custom_instructions` for preference extraction
- **PreferenceAnalysisAgent** — a NarrareAgent that performs periodic deep analysis of accumulated feedback (triggered at event thresholds: 20, 50, 100...), building a structured PreferenceProfile for LEARN-002 preparation
- **Frontend modify-tracking** — GenerationDraft detects when user edits AI text before accepting, sends action="modify" with diff
- **Frontend rating UI** — optional 1-5 star rating and rejection reason after accept/reject
- **Frontend preference profile page** — Settings → Learning tab showing style/content/constraint preferences, confidence score, event count, per-project selector, and reset button
- **Frontend learning status indicator** — "X/50 interactions" badge in GenerationPanel or MetadataSidebar
- **Comprehensive tests** — unit (FakeMemoryClient, FeedbackService, PreferenceService, PreferenceAnalysisAgent), integration (memory endpoints), frontend (feedback UI)

## Capabilities

### New Capabilities
- `embedding-cascade`: Multi-tier embedding resolution (OpenAI → provider-native → local sentence-transformers → disabled) with auto-detection from user's configured providers and explicit override via settings
- `preference-analysis-agent`: NarrareAgent that performs deep periodic analysis of accumulated feedback events, producing structured PreferenceProfile with style/content/constraint patterns and confidence scoring
- `feedback-loop-ui`: Frontend components for feedback collection (modify-tracking, rating, rejection reason), preference profile display (Settings → Learning), and learning status indicator

### Modified Capabilities
- `feedback-api`: Add `rating` field to feedback recording, add `POST /memory/analyze` endpoint for triggering PreferenceAnalysisAgent, enrich context with chapter/genre/mode
- `memory-layer`: Replace NullMemoryClient wiring with real AsyncMemory creation from user settings, add embedding cascade integration, add custom extraction instructions, add async mem0 processing via TaskIQ

## Impact

**Core layer (`packages/core/narrare_core/`):**
- `memory/mem0_client.py` — major rewrite: add embedding cascade resolver, user settings integration, custom instructions
- `memory/models.py` — add `rating` field to FeedbackEvent
- `memory/feedback_service.py` — enrich context, update translation for ratings
- `memory/preference_service.py` — refine queries for writing-specific preferences
- `agents/` — new `preference_analysis_agent.py` + `preference_analysis_types.py`
- `prompts/context.py` — already has fields, minor adjustments
- `llm/embeddings.py` — potentially extend for local embedding support

**Backend layer (`apps/api/narrare/`):**
- `memory/router.py` — replace NullMemoryClient with DI-injected real AsyncMemory
- `memory/schemas.py` — add rating field, context fields
- `memory/service.py` — add analysis endpoint handler
- `memory/models.py` — add rating column (migration)
- `settings/` — add embedding_provider/embedding_model fields to user_ai_settings
- New migration for rating column and embedding settings

**Frontend layer (`packages/web/`):**
- `components/studio/editor/GenerationDraft.tsx` — modify-tracking
- New `components/studio/learning/` — PreferenceProfile, LearningStatus, RatingUI
- `lib/api/memory.ts` — new API client for memory endpoints
- `lib/hooks/useMemory.ts` — TanStack Query hooks
- i18n keys for 3 locales

**Dependencies:**
- `sentence-transformers` — new dependency for local embedding fallback
- `mem0ai>=1.0` — already in dependencies, now actually used
- pgvector — already required

**Documentation:**
- LEARN-001 spec → status: implemented
- INFRA-005 spec → status: implemented
- ADR for embedding cascade decision
- TECH_STACK.md update for embedding strategy
