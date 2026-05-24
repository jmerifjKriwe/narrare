"""EmbeddingStore protocol and core data types.

Defines the platform-independent contract for embedding operations.
No database, HTTP, or framework dependencies — pure Protocol + dataclasses.

The API layer (apps/api/) implements this protocol with SQLAlchemy + pgvector.
Core layer consumes it via dependency injection.

See: docs/_shared/CONSTRAINTS.md (RULE-03 contracts first, RULE-07 dependency direction)
See: openspec/changes/infra-004-embedding-store/design.md (D7: Protocol in core)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single result from a vector similarity search.

    Attributes:
        source_id: UUID of the matched entity (kb_entry, chapter, etc.).
        source_type: Content type label (e.g. "kb_entry", "chapter").
        score: Similarity score in [0.0, 1.0]. Values outside this range
            are allowed for extensibility but should be documented by callers.
        content_hash: SHA-256 hex digest of the embedded content at the time
            of embedding generation. Used for dirty detection and cache
            validation.
    """

    source_id: UUID
    source_type: str
    score: float
    content_hash: str


@dataclass(frozen=True, slots=True)
class EmbeddingStats:
    """Aggregate embedding statistics for a single novel.

    Attributes:
        total: Total number of embeddable entities in the novel.
        embedded: Entities that have up-to-date embeddings.
        pending: Entities queued for embedding but not yet processed.
        failed: Entities whose embedding generation permanently failed.
        coverage_percentage: Ratio of embedded to total, expressed as
            a percentage (0.0-100.0). Computed as embedded/total * 100.
    """

    total: int
    embedded: int
    pending: int
    failed: int
    coverage_percentage: float


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbeddingStoreProtocol(Protocol):
    """Platform-independent contract for embedding storage and retrieval.

    Implementations live in the API layer (apps/api/narrare/embeddings/).
    Core services receive an instance via dependency injection and call
    through this protocol — never the concrete class directly.

    RULE-07: Dependencies flow one way. core/ never imports from apps/.
    RULE-03: Protocol exists before implementation.
    """

    async def generate(
        self,
        source_type: str,
        source_id: UUID,
        content: str,
    ) -> None:
        """Generate and store an embedding for the given content.

        Args:
            source_type: Content type label (e.g. "kb_entry").
            source_id: UUID of the source entity.
            content: Text content to embed.

        Raises:
            EmbeddingError: If generation or storage fails.
        """
        ...

    async def search(
        self,
        query: str,
        *,
        source_type: str | None = None,
        novel_id: UUID | None = None,
        threshold: float = 0.7,
        limit: int = 20,
        model: str | None = None,
    ) -> list[SearchResult]:
        """Search for similar content using vector similarity.

        Args:
            query: Text to search for (will be embedded).
            source_type: Optional filter by content type.
            novel_id: Required — limit results to entries in this novel.
            threshold: Minimum similarity score (default 0.7).
            limit: Maximum number of results (default 20, max 100).
            model: Embedding model to filter on. Defaults to active model.

        Returns:
            List of SearchResult sorted by similarity score descending.

        Raises:
            EmbeddingError: If query embedding generation fails.
        """
        ...

    async def delete(
        self,
        source_type: str,
        source_id: UUID,
    ) -> None:
        """Remove embeddings for a source entity.

        Args:
            source_type: Content type label.
            source_id: UUID of the source entity.
        """
        ...

    async def get_status(
        self,
        novel_id: UUID,
    ) -> EmbeddingStats:
        """Return embedding statistics for a novel.

        Args:
            novel_id: UUID of the novel.

        Returns:
            Aggregate embedding statistics.
        """
        ...

    async def reprocess(
        self,
        novel_id: UUID,
        model: str | None = None,
    ) -> None:
        """Re-generate embeddings for all content in a novel.

        Used when the embedding model changes or embeddings are stale.

        Args:
            novel_id: UUID of the novel.
            model: Optional model override. If None, uses the active model.
        """
        ...
