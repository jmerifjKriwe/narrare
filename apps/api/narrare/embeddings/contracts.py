"""Embedding repository contract — Protocol definitions.

Defines the interface for embedding persistence operations.
Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.models import Embedding
    from narrare_core.embeddings.store import EmbeddingStats


@runtime_checkable
class EmbeddingRepositoryProtocol(Protocol):
    """Protocol for embedding persistence operations.

    Implementations use raw SQL for pgvector compatibility.
    The repository only handles DB queries — no business logic.
    """

    async def upsert(
        self,
        source_type: str,
        source_id: UUID,
        content_hash: str,
        embedding: list[float],
        model: str,
        dimension: int,
    ) -> Embedding:
        """Insert or update an embedding row.

        Uses INSERT ON CONFLICT (source_type, source_id, model) DO UPDATE
        for pgvector-safe upsert.

        Args:
            source_type: Content type label (e.g. "kb_entry").
            source_id: UUID of the source entity.
            content_hash: SHA-256 hex digest of the embedded content.
            embedding: The embedding vector.
            model: Embedding model identifier.
            dimension: Dimension of the embedding vector.

        Returns:
            The upserted Embedding ORM object.
        """
        ...

    async def search(
        self,
        query_embedding: list[float],
        *,
        source_type: str | None = None,
        source_ids: set[UUID] | None = None,
        threshold: float = 0.7,
        limit: int = 20,
        model: str | None = None,
    ) -> list[tuple[Embedding, float]]:
        """Search for similar embeddings using cosine distance.

        Args:
            query_embedding: The query vector to compare against.
            source_type: Optional filter by content type.
            source_ids: Optional set of source UUIDs to restrict search to.
            threshold: Minimum cosine similarity (default 0.7).
            limit: Maximum number of results (default 20).
            model: Optional model filter.

        Returns:
            List of (Embedding, similarity_score) tuples ordered by
            similarity descending.
        """
        ...

    async def delete(
        self,
        source_type: str,
        source_id: UUID,
    ) -> None:
        """Delete all embeddings for a source entity.

        Args:
            source_type: Content type label.
            source_id: UUID of the source entity.
        """
        ...

    async def get_by_source(
        self,
        source_type: str,
        source_id: UUID,
        model: str | None = None,
    ) -> Embedding | None:
        """Fetch an embedding by source identity.

        Args:
            source_type: Content type label.
            source_id: UUID of the source entity.
            model: Optional model filter. If None, returns any model.

        Returns:
            The Embedding if found, else None.
        """
        ...

    async def get_status(
        self,
        source_type: str,
        source_ids: set[UUID],
    ) -> EmbeddingStats:
        """Compute embedding statistics for a set of source entities.

        Args:
            source_type: Content type label (e.g. "kb_entry").
            source_ids: Set of source entity UUIDs to check.

        Returns:
            Aggregate statistics including total, embedded, pending, failed.
        """
        ...

    async def batch_upsert(
        self,
        items: list[tuple[str, UUID, str, list[float], str, int]],
    ) -> int:
        """Insert or update multiple embedding rows in a single query.

        Args:
            items: List of tuples:
                (source_type, source_id, content_hash, embedding, model, dimension)

        Returns:
            Number of rows upserted.
        """
        ...
