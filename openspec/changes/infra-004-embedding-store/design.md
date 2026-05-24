## Context

Narrare's Knowledge Base needs semantic search for three upcoming features: proactive context suggestions (KB-005/INFRA-009), assisted entity creation with world context (KB-002), and entity extraction with deduplication (KB-007). The writing context assembler's "KB Suggested" tier currently has no embedding-based ranking. The `core/embeddings/` module is a stub. KB entries have an `embeddings_dirty` boolean flag with no pipeline to process it.

Existing infrastructure: pgvector/pgvector:pg17 in Docker Compose, `embed_texts()` in `core/llm/embeddings.py` for generation, `EmbeddingCascadeResolver` for provider selection. A `_scratch/api/narrare/embeddings/` implementation exists as architectural reference but references the old `kg_nodes` table.

RULE-20 applies: no half-implementations, no keyword-search fallback.

## Goals / Non-Goals

**Goals:**
- Generic embedding storage for multiple content types (kb_entry, chapter, chapter_summary, note)
- Background embedding generation via TaskIQ with priority queuing and retry
- Vector similarity search with hybrid ranking (cosine similarity + usage + recency)
- Content-hash dirty detection replacing boolean flags
- Two-phase model migration with side-by-side coexistence
- Admin API for embedding status and reprocessing
- Learning loop via `context_usage_events` for KB-005 accept/dismiss tracking
- 7 regression test scenarios for model migration safety

**Non-Goals:**
- Real-time embedding generation on save (too slow, blocks the write path)
- Embedding management UI (post-MVP)
- Cross-novel embedding search (embeddings are novel-scoped)
- Embedding visualization or exploration tools
- Custom embedding model training or fine-tuning

## Decisions

### D1: Generic `embeddings` table, not KB-specific

**Decision:** Single `embeddings` table with `source_type` + `source_id` columns.

**Alternatives considered:**
- KB-only `kb_embeddings` table: Would require a new table for every content type (chapters, notes). 3+ tables with identical schema, 3 vector indexes, 3 migrations on model change.
- EAV pattern with polymorphic association: More flexible but worse query performance and no HNSW index benefit.

**Rationale:** KB-005 searches across kb_entries, KB-007 deduplicates against kb_entries, and future features need chapter/summary embeddings. One table with `source_type` filter avoids table proliferation. The `UNIQUE(source_type, source_id, model)` constraint enables side-by-side model coexistence during migration.

### D2: Background generation via TaskIQ, not synchronous

**Decision:** On content save, set `embeddings_dirty` equivalent (content_hash comparison) and queue a TaskIQ task. No synchronous embedding API call in the write path.

**Alternatives considered:**
- Synchronous embedding on save: 200-500ms latency per save. Blocks the write path. Rate-limit issues on bulk operations.
- Webhook-based: More complex, no status tracking, harder to retry.

**Rationale:** Embeddings are ultimately consistent — they don't need to be available immediately after save. Background generation keeps the write path fast, enables batch processing, and provides retry with exponential backoff. Priority ordering (kb_entry > chapter > note) ensures important content is indexed first.

### D3: Hybrid search scoring formula

**Decision:** `score = 0.50 × similarity + 0.30 × usage + 0.20 × recency`

**Alternatives considered:**
- Pure cosine similarity: Ignores usage patterns and recency. Two characters mentioned in the same scene get similar scores even if one is irrelevant.
- Learned weights via ML: Over-engineering for current data volume. No training data for weight optimization.
- Fixed weight with no learning: No mechanism to improve suggestions over time.

**Rationale:** The 50/30/20 split is a well-established information retrieval pattern. Usage frequency captures behavioral signals (what the user actually references). Recency via exponential decay (`recency_score = 0.5^((now - last_referenced_at) / half_life_days)`) captures temporal relevance. The weights are configuration-friendly and can be tuned when usage data is available.

### D4: Content-hash dirty detection, not boolean flag

**Decision:** Store SHA-256 hash of the embedded content in `embeddings.content_hash`. On save, compare current content hash with stored hash. If different, queue re-embedding.

**Alternatives considered:**
- Boolean `embeddings_dirty` flag on source table: Requires modifying every source table (kb_entries, chapters, notes). Tight coupling.
- Timestamp comparison: Inaccurate — content could change twice within a second.

**Rationale:** Content hashes are source-agnostic (no schema changes on source tables), deterministic (same content = same hash = no re-embed), and enable idempotent batch processing (skip already-embedded content by hash comparison).

### D5: Two-phase model migration

**Decision:** When the embedding model changes, add a new `embedding_new VECTOR(new_dim)` column alongside the old one. Background task re-embeds all content into the new column. Cleanup migration drops old column and renames new.

**Alternatives considered:**
- `ALTER COLUMN TYPE vector(new_dim)`: pgvector does not support changing dimensions on an existing column. Would require dropping and recreating.
- Delete all embeddings and regenerate: System has no search capability during regeneration. Unacceptable downtime.
- Null column per model: Wastes storage, complicates queries with nullable vector columns.

**Rationale:** Side-by-side coexistence allows the system to remain operational during migration. Queries filter on `model = $active_model`, so old and new embeddings coexist without confusion. After all content is re-embedded, a cleanup migration drops the old column. This is the safest approach for production systems.

### D6: HNSW index, not IVFFlat

**Decision:** Use HNSW (Hierarchical Navigable Small World) index for vector similarity search.

**Alternatives considered:**
- IVFFlat: Requires training step with sufficient data. Bad recall with few vectors. Better for very large datasets (>1M rows) where approximate search is acceptable.
- Brute force (no index): Acceptable for <10K embeddings, but doesn't scale.

**Rationale:** HNSW has no training requirement, provides better recall at low query volumes (our use case: 5-20 suggestions per chapter open), and works well from the first embedding. Our expected scale (hundreds to low thousands of entries per novel) is well within HNSW's sweet spot.

### D7: EmbeddingStore Protocol in core, implementation in api

**Decision:** `EmbeddingStoreProtocol` in `core/embeddings/store.py` (no DB dependencies). `EmbeddingRepository` + `EmbeddingService` in `apps/api/narrare/embeddings/` (SQLAlchemy + pgvector).

**Rationale:** Follows RULE-07 (one-way dependencies: router → service → repository → database, service → core/llm). Core layer provides the contract; API layer implements it. No `AsyncSession` in core (RULE-07), no `sqlalchemy` imports in core.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Embedding API downtime blocks indexing | TaskIQ retry with exponential backoff. Content is still readable (embeddings_dirty but functional). Search falls back to name + graph traversal. |
| pgvector extension not available in dev | Docker Compose uses `pgvector/pgvector:pg17`. Integration tests skip if extension unavailable. |
| HNSW index build time on large datasets | Index built incrementally (each INSERT updates the index). No batch rebuild needed. |
| Model migration downtime | Two-phase: system runs on old column during migration. Zero downtime. |
| Large novels slow initial embedding | Priority queuing (kb_entry > chapter > note). Background processing. Partial search results acceptable during initial indexing. |
| content_hash SHA-256 collision probability | Negligible for text content. SHA-256 collision probability is ~2^-64 for our scale. |
| Hybrid search weight tuning | 0.50/0.30/0.20 as starting point. `context_usage_events` provides learning data for future optimization. Configurable via constants, not hardcoded. |

## Migration Plan

1. **Migration 0014**: Create `embeddings` table, `context_usage_events` table, add `last_referenced_at` and `usage_count` columns to `kb_entries`. HNSW index on `embeddings.embedding`.
2. **KB integration**: Modify `kb/service.py` to compute `content_hash` on save/update and queue TaskIQ embedding task.
3. **Backfill**: Existing kb_entries have no embeddings. Background task generates embeddings for all existing entries.
4. **Rollback**: Migration 0014 downgrade drops all new tables/columns. No data loss (embeddings can be regenerated).

## Open Questions

- **TaskIQ integration**: ADR-007 decided on TaskIQ but the background task infrastructure is not yet wired up. Sprint 1 assumes TaskIQ is available or a minimal task runner is created as part of this sprint. If TaskIQ is not ready, a simpler async task runner (e.g., `asyncio.create_task` with proper lifecycle management) can be used as an interim measure, but the TaskIQ interface must be the contract (RULE-20: build it properly).
- **Embedding dimension configuration**: Currently hardcoded at 1536 (text-embedding-3-small). Should this be a per-project or per-user setting? Recommendation: per-user via `user_ai_settings.embedding_model`, resolving through `EmbeddingCascadeResolver`. Validate in Sprint 1 if the settings schema needs extension.
