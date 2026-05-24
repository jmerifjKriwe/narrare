## ADDED Requirements

### Requirement: EmbeddingStore Protocol

The system SHALL provide an `EmbeddingStoreProtocol` in `core/embeddings/store.py` that defines the platform-independent interface for embedding operations.

The protocol SHALL define the following methods:
- `generate(source_type, source_id, content)` — Generate and store an embedding for the given content
- `search(query, source_type, novel_id, threshold, limit, model)` — Search for similar content using vector similarity
- `delete(source_type, source_id)` — Remove embeddings for a source entity
- `get_status(novel_id)` — Return embedding statistics for a novel
- `reprocess(novel_id, model)` — Re-generate embeddings for all content in a novel

The protocol SHALL be runtime-checkable (`@runtime_checkable`) and have no database or HTTP dependencies.

#### Scenario: Protocol conformance
- **WHEN** a class implements all methods of `EmbeddingStoreProtocol`
- **THEN** `isinstance(instance, EmbeddingStoreProtocol)` SHALL return `True`

#### Scenario: Protocol is importable from core without database imports
- **WHEN** `EmbeddingStoreProtocol` is imported from `narrare_core.embeddings.store`
- **THEN** no `sqlalchemy`, `asyncpg`, or `fastapi` imports are triggered

---

### Requirement: Generic Embedding Table

The system SHALL store embeddings in a `embeddings` table with the following schema:

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY, DEFAULT gen_random_uuid() |
| source_type | TEXT | NOT NULL |
| source_id | UUID | NOT NULL |
| content_hash | TEXT | NOT NULL |
| embedding | VECTOR(1536) | NOT NULL |
| model | TEXT | NOT NULL |
| dimension | INT | NOT NULL |
| generated_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

The table SHALL have a `UNIQUE(source_type, source_id, model)` constraint enabling side-by-side model coexistence.

An HNSW index SHALL be created on the `embedding` column using `vector_cosine_ops`.
A B-tree index SHALL be created on `(source_type, source_id)`.

#### Scenario: Side-by-side model coexistence
- **WHEN** embeddings for model "text-embedding-3-small" and "text-embedding-3-large" exist for the same source
- **THEN** both rows exist in the table with different `model` values
- **AND** queries filtering on `model = $active_model` return only results for that model

#### Scenario: Unique constraint prevents duplicate embeddings
- **WHEN** an embedding for source_type="kb_entry", source_id=X, model="text-embedding-3-small" already exists
- **THEN** inserting another row with the same (source_type, source_id, model) SHALL fail with a unique constraint violation

---

### Requirement: Content Hash Dirty Detection

The system SHALL use SHA-256 content hashing to detect stale embeddings, replacing the boolean `embeddings_dirty` flag approach.

On save/update of any embeddable content, the system SHALL compute `hashlib.sha256(content.encode()).hexdigest()` and compare it with the stored `content_hash` in the `embeddings` table. If the hashes differ (or no embedding exists), the system SHALL queue an embedding generation task.

#### Scenario: Content unchanged — no re-embedding
- **WHEN** a kb_entry is saved with content identical to the last saved version
- **THEN** the stored `content_hash` matches the computed hash
- **AND** no embedding generation task is queued

#### Scenario: Content changed — re-embedding triggered
- **WHEN** a kb_entry is saved with modified content
- **THEN** the computed content hash differs from the stored hash
- **AND** an embedding generation task is queued with appropriate priority

#### Scenario: New entry — embedding generated
- **WHEN** a new kb_entry is created
- **THEN** no embedding row exists for this source
- **AND** an embedding generation task is queued

---

### Requirement: Background Embedding Generation

The system SHALL generate embeddings asynchronously via TaskIQ background tasks.

On content save/update, the system SHALL queue a TaskIQ task with the following parameters:
- `source_type`: The content type (kb_entry, chapter, etc.)
- `source_id`: The UUID of the entity
- `priority`: Integer priority (0=highest, kb_entry=0, chapter=1, note=2)

The background task SHALL:
1. Load the content for the given source
2. Compute the content hash
3. Compare with stored hash — if identical, skip (idempotent)
4. Call `embed_texts()` to generate the embedding vector
5. UPSERT the embedding into the `embeddings` table
6. On failure: retry with exponential backoff (max 3 retries, delays: 30s, 120s, 300s)
7. On permanent failure: log error, leave `content_hash` stale (will be retried on next save)

#### Scenario: Successful embedding generation
- **WHEN** a kb_entry is saved with new content
- **THEN** a TaskIQ task is queued with priority=0
- **AND** the task generates an embedding via `embed_texts()`
- **AND** the embedding row is upserted with `model`, `dimension`, `content_hash`, and `generated_at`

#### Scenario: Embedding API failure with retry
- **WHEN** the embedding generation API call fails
- **THEN** the task retries up to 3 times with exponential backoff
- **AND** on final failure, logs the error without crashing

#### Scenario: Idempotent embedding generation
- **WHEN** an embedding task is queued for content that has not changed since the last embedding
- **THEN** the task computes the content hash, finds it matches the stored hash
- **AND** skips embedding generation (no API call, no database write)

---

### Requirement: Vector Similarity Search

The system SHALL provide vector similarity search via pgvector's cosine distance operator.

The search endpoint SHALL accept:
- `query`: Text to search for (will be embedded)
- `source_type`: Optional filter (e.g., "kb_entry")
- `novel_id`: Required — limit results to entries belonging to the novel
- `threshold`: Minimum similarity score (default 0.7)
- `limit`: Maximum results (default 20, max 100)
- `model`: Model to filter on (default: active model from settings)

The search SHALL return results ordered by similarity score (descending), each containing:
- `source_id`: UUID of the matched entity
- `source_type`: Content type
- `score`: Similarity score (0-1)
- `content_hash`: Hash of the embedded content (for cache validation)

#### Scenario: Search returns relevant results
- **WHEN** searching for "forest dwelling creature" in a novel with akb_entry about "The Forest Spirit"
- **THEN** the search SHALL return the kb_entry with a similarity score above the threshold
- **AND** the result SHALL include source_id, source_type, and score

#### Scenario: Search filters by source type
- **WHEN** searching with source_type="kb_entry"
- **THEN** only kb_entry embeddings SHALL be returned
- **AND** chapter or note embeddings SHALL be excluded

#### Scenario: Search with no matching embeddings
- **WHEN** searching for content that has no embeddings above the threshold
- **THEN** an empty list SHALL be returned
- **AND** no error SHALL be raised

---

### Requirement: Hybrid Search Scoring

The system SHALL rank search results using a hybrid scoring formula:

`score = 0.50 × similarity + 0.30 × usage_score + 0.20 × recency_score`

Where:
- `similarity`: Cosine similarity from pgvector (0-1)
- `usage_score`: Normalized usage count. `min(usage_count / max_usage, 1.0)` where `max_usage` is the maximum usage count among candidates (or 1.0 if all are 0)
- `recency_score`: Exponential time decay. `0.5^((now - last_referenced_at) / half_life_days)` where `half_life_days = 14`. Entries never referenced get `recency_score = 0.1` (slight baseline)

The weighting coefficients (0.50, 0.30, 0.20) SHALL be configurable constants, not hardcoded in business logic.

#### Scenario: Hybrid ranking with usage and recency
- **WHEN** three kb_entries match a query with similarity 0.9, 0.85, 0.7
- **AND** entry 1 has usage_count=10, last_referenced=1 day ago
- **AND** entry 2 has usage_count=0, last_referenced=never
- **AND** entry 3 has usage_count=50, last_referenced=7 days ago
- **THEN** the final ranking SHALL incorporate all three signals
- **AND** entry 3 (high usage) MAY rank higher than entry 1 despite lower similarity

#### Scenario: All entries have zero usage
- **WHEN** all candidate entries have `usage_count = 0` and `last_referenced_at = NULL`
- **THEN** `usage_score` SHALL be 0 for all entries
- **AND** `recency_score` SHALL be 0.1 for all entries (baseline)
- **AND** ranking SHALL be based on similarity only (0.50 × similarity + 0.30 × 0 + 0.20 × 0.1)

---

### Requirement: Context Usage Events

The system SHALL track user feedback on proactive suggestions via a `context_usage_events` table:

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PRIMARY KEY |
| novel_id | UUID | NOT NULL, REFERENCES novels(id) |
| entry_id | UUID | NOT NULL, REFERENCES kb_entries(id) |
| chapter_id | UUID | REFERENCES chapters(id) |
| action | TEXT | NOT NULL — "accepted", "dismissed", "pinned", "unpinned" |
| source | TEXT | NOT NULL — "proactive", "search", "manual" |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

When a user accepts a suggestion, the system SHALL also increment `kb_entries.usage_count` and update `kb_entries.last_referenced_at`.

#### Scenario: User accepts a suggestion
- **WHEN** a proactive suggestion for kb_entry X is accepted
- **THEN** a `context_usage_events` row with action="accepted", source="proactive" is created
- **AND** `kb_entries.usage_count` for entry X is incremented by 1
- **AND** `kb_entries.last_referenced_at` for entry X is set to now()

#### Scenario: User dismisses a suggestion
- **WHEN** a proactive suggestion for kb_entry Y is dismissed
- **THEN** a `context_usage_events` row with action="dismissed", source="proactive" is created
- **AND** `kb_entries.usage_count` and `last_referenced_at` for entry Y are NOT modified

---

### Requirement: Two-Phase Model Migration

The system SHALL support changing the embedding model without downtime via a two-phase migration.

**Phase 1 — Add new column:**
- Alembic migration adds `embedding_new VECTOR(new_dim)` column (nullable)
- New HNSW index on `embedding_new`
- Application reads from old `embedding` column, writes to `embedding_new` for new model
- Background task re-embeds all content with the new model

**Phase 2 — Cleanup:**
- After all content is re-embedded, a cleanup migration:
  1. Drops the old `embedding` column
  2. Renames `embedding_new` to `embedding`
  3. Drops the old HNSW index
  4. Renames the new HNSW index to `idx_embeddings_search`

During migration, search queries filter on `model = $active_model`.

#### Scenario: Phase 1 — new embeddings use new model
- **WHEN** model is changed to "text-embedding-3-large" (3072d)
- **AND** Phase 1 migration has been applied
- **THEN** new embedding tasks write to `embedding_new` with model="text-embedding-3-large"
- **AND** search queries filter on `model = 'text-embedding-3-large'` using `embedding_new`
- **AND** old embeddings in `embedding` (model="text-embedding-3-small") are still queryable

#### Scenario: Phase 2 — cleanup after re-embedding
- **WHEN** all content has been re-embedded with the new model
- **THEN** the cleanup migration drops `embedding` and renames `embedding_new` to `embedding`
- **AND** the HNSW index is recreated on the renamed column
- **AND** search queries work on the single `embedding` column

#### Scenario: Migration rollback safety
- **WHEN** Phase 1 migration fails or is rolled back
- **THEN** `embedding_new` column is dropped
- **AND** `embedding` column with old model remains intact and functional
- **AND** the old HNSW index still works

---

### Requirement: Admin Embedding API

The system SHALL provide admin API endpoints for embedding management:

- `GET /api/v1/admin/embeddings/status/{novel_id}` — Return embedding statistics (total entries, embedded count, pending count, failed count, coverage percentage)
- `POST /api/v1/admin/embeddings/reprocess/{novel_id}` — Trigger re-embedding for all content in a novel (with optional `model` parameter for model change)
- `GET /api/v1/admin/embeddings/model` — Return the currently active embedding model and dimension

#### Scenario: Check embedding status
- **WHEN** requesting status for a novel with 100 kb_entries, 80 of which have embeddings
- **THEN** the response SHALL include `total=100`, `embedded=80`, `pending=15`, `failed=5`, `coverage=80.0`

#### Scenario: Trigger reprocessing
- **WHEN** requesting reprocess for a novel
- **THEN** all content with stale or missing embeddings SHALL be queued for generation
- **AND** a background task status SHALL be returned (task_id)

---

### Requirement: Embedding Cascade Integration

The system SHALL use the existing `EmbeddingCascadeResolver` (ADR-017) to determine the embedding provider and model for each user/project.

The embedding generation pipeline SHALL:
1. Resolve the embedding provider via `EmbeddingCascadeResolver.resolve()`
2. Use the resolved `EmbeddingConfig` to call `embed_texts()` with the correct model and API key
3. Store the model name and dimension alongside the embedding vector

#### Scenario: OpenAI provider configured
- **WHEN** the user has an OpenAI API key configured
- **THEN** embeddings SHALL be generated using OpenAI's text-embedding-3-small (or the user's configured model)
- **AND** the `model` field SHALL be "text-embedding-3-small"
- **AND** the `dimension` field SHALL be 1536

#### Scenario: Local model configured
- **WHEN** no cloud provider is available and local embeddings are configured
- **THEN** the cascade SHALL fall back to local sentence-transformers
- **AND** the model and dimension SHALL reflect the local model used
