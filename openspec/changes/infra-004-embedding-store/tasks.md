## 1. Core Layer — EmbeddingStore Protocol

- [ ] 1.1 Create `packages/core/narrare_core/embeddings/store.py` with `EmbeddingStoreProtocol` (generate, search, delete, get_status, reprocess) and `SearchResult`, `EmbeddingStats` dataclasses
- [ ] 1.2 Create `packages/core/narrare_core/embeddings/__init__.py` (update from stub to export protocol and dataclasses)
- [ ] 1.3 Write unit tests for `EmbeddingStoreProtocol` conformance and dataclass validation

## 2. Core Layer — Content Hash Utility

- [ ] 2.1 Create `packages/core/narrare_core/embeddings/hash.py` with `compute_content_hash(content: str) -> str` (SHA-256)
- [ ] 2.2 Write unit tests for content hash computation (identical content = identical hash, different content = different hash, empty string handling)

## 3. API Layer — Database Schema

- [ ] 3.1 Create Alembic migration `0014_embeddings.py`: `embeddings` table (id, source_type, source_id, content_hash, embedding VECTOR(1536), model, dimension, generated_at), `UNIQUE(source_type, source_id, model)`, HNSW index, B-tree index on (source_type, source_id)
- [ ] 3.2 Add `context_usage_events` table to migration 0014 (id, novel_id, entry_id, chapter_id, action, source, created_at) with indexes on entry_id and novel_id+created_at
- [ ] 3.3 Add `last_referenced_at TIMESTAMPTZ NULL` and `usage_count INT DEFAULT 0` columns to `kb_entries` in migration 0014
- [ ] 3.4 Write schema regression test: verify migration 0014 creates all tables, columns, indexes, and constraints correctly

## 4. API Layer — Embedding Models

- [ ] 4.1 Create `apps/api/narrare/embeddings/__init__.py` (module init)
- [ ] 4.2 Create `apps/api/narrare/embeddings/models.py` with `Embedding` SQLAlchemy model (id, source_type, source_id, content_hash, embedding, model, dimension, generated_at) and `ContextUsageEvent` model
- [ ] 4.3 Register `Embedding` and `ContextUsageEvent` models in Alembic `env.py` for autogenerate support

## 5. API Layer — EmbeddingRepository

- [ ] 5.1 Create `apps/api/narrare/embeddings/contracts.py` with `EmbeddingRepositoryProtocol` (upsert, search, delete, get_by_source, get_status, batch_upsert)
- [ ] 5.2 Create `apps/api/narrare/embeddings/repository.py` implementing `EmbeddingRepositoryProtocol` with CRUD, vector similarity search (cosine), hybrid search (similarity + metadata filter), content_hash dedup via UPSERT, and batch operations
- [ ] 5.3 Write repository integration tests: CRUD, vector_search with real pgvector, hybrid_search with score calculation, batch_upsert, content_hash dedup

## 6. API Layer — EmbeddingService

- [ ] 6.1 Create `apps/api/narrare/embeddings/service.py` with `EmbeddingService` (generate, search, delete, get_status, reprocess) orchestrating repository + `embed_texts()` + cascade resolver
- [ ] 6.2 Create `apps/api/narrare/embeddings/dependencies.py` with FastAPI DI factories
- [ ] 6.3 Write service unit tests: generate delegates to embed_texts + repo.upsert, search calls hybrid ranking, delete cascades properly, error recovery on API failure

## 7. API Layer — Background Tasks

- [ ] 7.1 Create `apps/api/narrare/embeddings/tasks.py` with TaskIQ task definitions: `embed_source(source_type, source_id, priority)` with retry (max 3, exponential backoff: 30s, 120s, 300s) and priority queuing
- [ ] 7.2 Implement content_hash comparison in task: skip generation if hash matches stored value (idempotent)
- [ ] 7.3 Add `embeddings_dirty` removal from `kb_entries` model (replace with content_hash check) — update `kb/service.py` save/update hooks to compute content_hash and queue TaskIQ task
- [ ] 7.4 Write task integration tests: successful generation, API failure with retry, idempotent skip on unchanged content, priority ordering

## 8. API Layer — Admin Router

- [ ] 8.1 Create `apps/api/narrare/embeddings/router.py` with admin endpoints: `GET /admin/embeddings/status/{novel_id}`, `POST /admin/embeddings/reprocess/{novel_id}`, `GET /admin/embeddings/model`
- [ ] 8.2 Create `apps/api/narrare/embeddings/schemas.py` with Pydantic request/response schemas for admin endpoints
- [ ] 8.3 Write router integration tests for all three admin endpoints

## 9. API Layer — Hybrid Search Scoring

- [ ] 9.1 Create `packages/core/narrare_core/embeddings/scoring.py` with `rank_candidates()` implementing the hybrid formula: `0.50 × similarity + 0.30 × usage + 0.20 × recency` with configurable coefficients and exponential time decay (half_life_days=14)
- [ ] 9.2 Write unit tests for scoring: known inputs produce expected scores, zero-usage baseline, recency decay calculation, coefficient configurability

## 10. API Layer — KB Integration Hooks

- [ ] 10.1 Update `kb/service.py`: on `create()` and `update()`, compute content hash and queue `embed_source` TaskIQ task
- [ ] 10.2 Update `kb/models.py`: add `last_referenced_at` and `usage_count` columns (remove `embeddings_dirty` if no longer needed)
- [ ] 10.3 Write integration tests: kb_entry create triggers embedding task, kb_entry update triggers re-embedding when content changed, kb_entry update with unchanged content skips re-embedding

## 11. API Layer — Context Usage Events

- [ ] 11.1 Create `apps/api/narrare/kb/suggest_contracts.py` (or add to `kb/contracts.py`) with `ContextUsageProtocol` (record_accept, record_dismiss, get_usage_stats)
- [ ] 11.2 Create `apps/api/narrare/kb/usage_service.py` implementing `ContextUsageProtocol`: record accept (insert event + increment usage_count + update last_referenced_at), record dismiss (insert event only, no usage update)
- [ ] 11.3 Write usage service unit tests: accept increments usage_count and updates last_referenced_at, dismiss does not update usage, double-accept increments twice

## 12. Model Migration Tests

- [ ] 12.1 Create `tests/integration/embeddings/test_embedding_migration.py` with 7 regression scenarios: side-by-side coexistence, search continuity during migration, full re-embed, partial failure recovery, content drift detection, dimension DDL migration, rollback safety
- [ ] 12.2 Create `tests/integration/embeddings/test_two_phase_migration.py` with 2 scenarios: Phase 1 system remains operational, Phase 2 cleanup removes old column

## 13. Final Validation

- [ ] 13.1 Run `scripts/check_architecture.py` — verify no constraint violations in new modules
- [ ] 13.2 Run full test suite — all existing tests pass, new tests pass
- [ ] 13.3 Update `docs/_shared/CURRENT_STATE.md` with INFRA-004 implementation status
- [ ] 13.4 Update feature spec `docs/features/infra/INFRA-004-embedding-store.md` status to `in progress`
