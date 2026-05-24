"""pgvector abstraction layer for embeddings.

Provides a clean interface for storing and querying vector embeddings
via PostgreSQL's pgvector extension. All embedding storage and similarity
search operations go through this module.

Core types and utilities (no database dependencies):
- EmbeddingStoreProtocol: Contract for embedding operations
- SearchResult / EmbeddingStats: Data types for search and status
- compute_content_hash: SHA-256 dirty detection
- rank_candidates / ScoringConfig: Hybrid search scoring

See: docs/_shared/CONSTRAINTS.md (RULE-08 — pgvector in core/embeddings/ only)
See: openspec/changes/infra-004-embedding-store/design.md (D7: Protocol in core)
"""

from __future__ import annotations

from narrare_core.embeddings.hash import compute_content_hash
from narrare_core.embeddings.scoring import ScoredCandidate, ScoringConfig, rank_candidates
from narrare_core.embeddings.store import EmbeddingStats, EmbeddingStoreProtocol, SearchResult

__all__ = [
    "EmbeddingStats",
    "EmbeddingStoreProtocol",
    "ScoredCandidate",
    "ScoringConfig",
    "SearchResult",
    "compute_content_hash",
    "rank_candidates",
]
