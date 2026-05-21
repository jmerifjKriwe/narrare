## Context

The memory layer (INFRA-005) was implemented as infrastructure: protocols, models, services, API endpoints, and a `NullMemoryClient` for graceful degradation. The feedback loop described in LEARN-001 cannot function because `memory/router.py` instantiates `NullMemoryClient` instead of a real mem0 `AsyncMemory`. The core extraction → storage → retrieval → injection pipeline exists in code but is dead — preferences are always empty.

A critical constraint emerged during exploration: users may have only a single LLM provider configured, and that provider may not offer an embedding API. z.ai has no `/v1/embeddings` endpoint. Anthropic has no embedding API either. Only OpenAI and Ollama provide embeddings. The memory system must work regardless of which single provider the user chose during setup.

The existing SET-003 model configuration system already implements a cascade pattern (project → user → default) with explicit overrides. The embedding resolution follows the same architectural pattern.

## Goals / Non-Goals

**Goals:**
- Close the feedback loop: record → extract → store → retrieve → inject → better suggestions
- Make mem0 work with real AsyncMemory, not NullMemoryClient
- Support single-provider users (z.ai, Anthropic, OpenAI, Ollama) via embedding cascade
- Non-blocking feedback processing (async via TaskIQ, per ADR-012)
- Structured preference analysis via PreferenceAnalysisAgent (LEARN-002 preparation)
- Full frontend feedback collection (modify-tracking, rating, rejection reasons)
- Preference profile UI in Settings
- Zero data loss: PostgreSQL audit trail + mem0 semantic storage

**Non-Goals:**
- LEARN-002 style adaptation (deep voice analysis, few-shot prompting) — that's a separate change
- Embedding provider auto-detection beyond OpenAI — Stufe 2 (provider-native embeddings) is a future hook, not implemented now
- Real-time preference updates in the UI — preferences update on next generation, not via WebSocket
- Cross-user learning — preferences are strictly per-user, per-project
- Embedding model fine-tuning — we use off-the-shelf models

## Decisions

### Decision 1: mem0 AsyncMemory with embedding cascade (not custom preference system)

**Choice:** Keep mem0, add 4-tier embedding cascade.

**Alternatives considered:**
- Custom preference system without mem0 (no embeddings needed) — simpler but loses semantic search, deduplication, and future-proofing for LEARN-002/ANAL-007. Would need to be rebuilt when semantic search becomes necessary.
- mem0 with only OpenAI embeddings — violates single-provider constraint for z.ai/Anthropic users.
- mem0 with only local embeddings — works but wastes quality when OpenAI is available.

**Rationale:** The cascade gives the best embedding quality available while guaranteeing functionality for every user. sentence-transformers as Stufe 3 is the safety net — not the default. mem0 provides extraction, dedup, semantic search, and scoping that we'd otherwise have to build ourselves. The existing 800+ lines of mem0-oriented code stay useful.

### Decision 2: Embedding cascade integrated into SET-003 settings

**Choice:** Add `embedding_provider` ("auto" | "openai" | "local" | "disabled") and `embedding_model` to `user_ai_settings`. Auto-cascade is default.

**Rationale:** SET-003 already implements cascade-style configuration (project → user → default). Embedding configuration follows the same pattern. Users can explicitly choose, but auto-cascade handles it correctly in 99% of cases. The UI shows which tier is currently active (e.g., "Currently using: Local (sentence-transformers)").

### Decision 3: Async mem0 processing via TaskIQ (not synchronous in request)

**Choice:** `POST /memory/feedback` writes to PostgreSQL synchronously, then publishes a `FeedbackRecorded` event. A TaskIQ worker calls `mem0.add()` asynchronously.

**Rationale:** mem0.add() makes an LLM call (extraction) + embedding call. This takes 1-3 seconds. Blocking the HTTP response for that is unacceptable. ADR-012 already defines the event-driven pattern. The PostgreSQL write guarantees no data loss — if the TaskIQ task fails, the event is still in the audit trail and can be reprocessed.

### Decision 4: PreferenceAnalysisAgent for deep periodic analysis

**Choice:** A NarrareAgent (per `how-to-add-an-agent.md`) that runs at event thresholds (20, 50, 100, 200...) and produces a structured PreferenceProfile.

**Rationale:** mem0's per-event extraction is good for individual facts ("User rejected a continuation: too wordy"). But it doesn't synthesize cross-patterns ("User consistently shortens suggestions by 20-30%, suggesting preference for concise prose"). The PreferenceAnalysisAgent takes accumulated feedback events, runs one batch LLM call, and produces a richer profile. This is the foundation for LEARN-002 — the agent will be extended later for deep style analysis.

### Decision 5: sentence-transformers as dependency for local embeddings

**Choice:** Add `sentence-transformers` to core dependencies. Use `all-MiniLM-L6-v2` (~80MB) as the local embedding model.

**Alternatives considered:**
- Require users to configure a separate embedding provider — bad UX, violates single-provider constraint.
- Use pgvector's built-in vector operations without embeddings — no semantic search.
- Use a lighter embedding library — sentence-transformers is the standard, well-maintained, and mem0 supports it natively.

**Rationale:** The model is downloaded once on first use. It's free, runs locally, and provides good enough quality for preference matching. It's the Stufe 3 fallback — only used when OpenAI is not available.

### Decision 6: mem0 client lifecycle — per-user singleton with cache

**Choice:** Cache mem0 AsyncMemory clients per user_id in a bounded LRU cache. Client is created on first feedback/preference request and reused until provider settings change.

**Rationale:** Creating an AsyncMemory instance involves config validation and potential connection setup. Doing this per request is wasteful. The cache is bounded (e.g., 100 users) with TTL eviction. When the user changes their provider settings, the cache entry is invalidated.

## Risks / Trade-offs

**[sentence-transformers dependency size]** → Mitigation: Model downloaded on first use (~80MB), not at install time. If even this fails, NullMemoryClient kicks in (Stufe 4).

**[mem0 extraction LLM cost]** → Mitigation: Use cost-efficient models (glm-4-flash, claude-haiku, gpt-4.1-nano). Feedback text is short (<200 chars), so extraction tokens are minimal. Async processing means user never waits.

**[mem0 stability / version churn]** → Mitigation: NullMemoryClient fallback at every level. If mem0 raises, feedback is still in PostgreSQL. Pin mem0 version in dependencies.

**[Cold start: first 20 interactions have no preferences]** → Mitigation: Frontend shows learning progress ("12/50 interactions"). PromptComposer handles empty preferences gracefully (already implemented).

**[Over-optimization: AI becomes too predictable]** → Mitigation: PreferenceAnalysisAgent includes a "variety" dimension. Constraints are injected as soft guidance, not hard rules. Users can reset preferences per project.

**[Embedding quality inconsistency across tiers]** → Mitigation: Local embeddings (Stufe 3) are good enough for preference matching — we're not doing RAG over documents, we're matching "prefers concise prose" to "prefers short sentences". The quality difference matters less here than in knowledge retrieval.
