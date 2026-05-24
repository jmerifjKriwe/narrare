## MODIFIED Requirements

### Requirement: KB Entry persistence hooks

The system SHALL compute a content hash on every kb_entry save or update and queue an embedding generation task when the content has changed.

On `KBService.create()`:
1. Compute `hashlib.sha256(content.encode()).hexdigest()`
2. Queue TaskIQ task: `embed_source(source_type="kb_entry", source_id=entry.id)`

On `KBService.update()`:
1. Compute new content hash
2. Compare with stored hash in `embeddings` table (query by source_type + source_id)
3. If hash differs or no embedding exists: queue TaskIQ task: `embed_source(source_type="kb_entry", source_id=entry.id)`

The embedding task queuing SHALL be non-blocking — failures to queue SHALL be logged but SHALL NOT prevent the save/update operation from completing.

#### Scenario: New kb_entry triggers embedding generation
- **WHEN** a new kb_entry is created via `KBService.create()`
- **THEN** a TaskIQ task SHALL be queued with `source_type="kb_entry"` and `source_id=<new_entry_id>`
- **AND** the creation response SHALL NOT be delayed by embedding generation

#### Scenario: Updated kb_entry with changed content triggers re-embedding
- **WHEN** an existing kb_entry is updated with modified content
- **AND** the new content hash differs from the stored hash
- **THEN** a TaskIQ task SHALL be queued for re-embedding

#### Scenario: Updated kb_entry with unchanged content — no re-embedding
- **WHEN** an existing kb_entry is updated with content identical to the current version
- **AND** the computed content hash matches the stored hash
- **THEN** no embedding task SHALL be queued

#### Scenario: Embedding task queue failure does not block save
- **WHEN** the TaskIQ task queue is unavailable
- **THEN** the kb_entry save/update SHALL complete successfully
- **AND** the task queue failure SHALL be logged as a warning
- **AND** the entry will be embedded on the next save or manual reprocess

---

## ADDED Requirements

### Requirement: KB Entry usage tracking columns

The `kb_entries` table SHALL include two new columns:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| last_referenced_at | TIMESTAMPTZ | NULL | Timestamp of last proactive suggestion acceptance |
| usage_count | INT | 0 | Number of times this entry was accepted from a proactive suggestion |

These columns SHALL be updated by the KB-005/INFRA-009 Proactive Context service when a user accepts or dismisses a suggestion (see embedding-store spec: Context Usage Events).

#### Scenario: New kb_entry has zero usage
- **WHEN** a new kb_entry is created
- **THEN** `usage_count` SHALL be 0
- **AND** `last_referenced_at` SHALL be NULL

#### Scenario: Accepting a suggestion updates usage
- **WHEN** a proactive suggestion for kb_entry X is accepted
- **THEN** `usage_count` for entry X SHALL increment by 1
- **AND** `last_referenced_at` for entry X SHALL be set to the current timestamp
