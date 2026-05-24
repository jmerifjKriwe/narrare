## Why

Narrare's KB features (suggestions, assisted creation, entity extraction) and its writing context pipeline all need semantic search over KB entries, chapters, and other content. Currently there is no embedding store — the `core/embeddings/` module is a stub, KB entries have an `embeddings_dirty` flag with no pipeline to process it, and the context assembler's "KB Suggested" tier has no embedding-based ranking. Three planned features (KB-002 Assisted Creation, KB-005/INFRA-009 Proactive Context, KB-007 Extraction) are blocked on this infrastructure. Building it properly now unblocks the entire KB feature roadmap.

## What Changes

- **New generic `embeddings` table** with `source_type` (kb_entry, chapter, chapter_summary, note) + `source_id` + `content_hash` + `vector(1536)` + `model` + HNSW index. Replaces the per-entity `embeddings_dirty` boolean flag approach.
- **New `EmbeddingStoreProtocol` in `core/embeddings/store.py`** — platform-independent interface for generate, search, delete, status, reprocess.
- **New `EmbeddingRepository` and `EmbeddingService` in `apps/api/narrare/embeddings/`** — CRUD, vector search, hybrid search (cosine similarity + metadata filters), batch operations, content-hash dirty detection.
- **Background embedding generation via TaskIQ** — queued on content save with priority (kb_entry > chapter > note), retry with exponential backoff, status tracking.
- **New `context_usage_events` table** for KB-005's learning loop (accept/dismiss/pin tracking).
- **New columns on `kb_entries`**: `last_referenced_at TIMESTAMPTZ`, `usage_count INT DEFAULT 0`.
- **Hybrid search scoring formula**: 0.50 × similarity + 0.30 × usage + 0.20 × recency.
- **Two-phase model migration strategy** — add new dimension column, re-embed in background, cleanup migration. 7 regression test scenarios.
- **Integration hooks in KB service** — on save/update, compute content_hash, queue embedding task.
- **Admin API endpoints** — embedding status per novel, reprocess trigger, model info.

## Capabilities

### New Capabilities
- `embedding-store`: Generic embedding generation, storage, and vector similarity search with hybrid ranking, background generation via TaskIQ, content-hash dirty detection, and two-phase model migration.

### Modified Capabilities
- `kb-management`: Add `last_referenced_at` and `usage_count` columns to kb_entries. Hook embedding generation into save/update lifecycle (queue TaskIQ task on content change).

## Impact

- **Database**: New `embeddings` table (Alembic migration 0014), new `context_usage_events` table, two new columns on `kb_entries`.
- **Core**: New `EmbeddingStoreProtocol` in `core/embeddings/store.py`. Existing `core/llm/embeddings.py` (`embed_texts`) used as generation function.
- **API**: New `apps/api/narrare/embeddings/` module (models, repository, service, router, dependencies, tasks). Modified `kb/service.py` to queue embedding tasks on save/update.
- **Dependencies**: TaskIQ for background tasks (ADR-007 already decided). pgvector extension already in Docker Compose.
- **Infra**: Docker Compose already uses `pgvector/pgvector:pg17`. No new infrastructure needed.
- **Blockers unblocked**: KB-005/INFRA-009 (Proactive Context), KB-002 (Assisted Creation world context), KB-007 (Extraction dedup).
