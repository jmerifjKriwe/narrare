"""pgvector abstraction layer for embeddings.

Provides a clean interface for storing and querying vector embeddings
via PostgreSQL's pgvector extension. All embedding storage and similarity
search operations go through this module.

Planned features:
- Embedding store with upsert and batch operations
- Semantic similarity search with configurable thresholds
- KB entry deduplication via embedding distance
- Hybrid search (vector + keyword) for KB queries

See: docs/architecture/questions/ (Q-003 — embedding strategy)
See: docs/_shared/CONSTRAINTS.md (RULE-08 — pgvector in core/embeddings/ only)
"""
