"""Embedding repository contract — Protocol definitions.

Defines the interface for embedding persistence operations.
Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from narrare.embeddings.models import Embedding
    from narrare.embeddings.search_queries import SearchRow
    from narrare_core.embeddings.store import EmbeddingStats

# ---------------------------------------------------------------------------
# Governed defaults for embedding vector search — CR-AUFG-08-13.
#
# Single definition site (RULE-06). The repository, service, and query
# builder import these instead of duplicating the literals, so there is one
# place to review when a default changes. See the Governed Defaults Manifest
# §4.1 for rationale and review triggers.
# ---------------------------------------------------------------------------
DEFAULT_EMBEDDING_SEARCH_THRESHOLD: float = 0.7
DEFAULT_EMBEDDING_SEARCH_LIMIT: int = 20

type TextFetcher = Callable[[Sequence[UUID]], Awaitable[dict[UUID, str]]]
"""Async candidate-text supplier for the rerank stage (ADR-090 Decision 4).

Search rows carry no text, so the DI layer injects this fetcher (a closure
over the session + KB repository); the rerank stage calls it with the
candidate source ids and expects ``{source_id: text}`` — ids absent from
the mapping are treated as textless and keep their first-stage position.
"""


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
        threshold: float = DEFAULT_EMBEDDING_SEARCH_THRESHOLD,
        limit: int = DEFAULT_EMBEDDING_SEARCH_LIMIT,
        model: str | None = None,
        novel_id: UUID | None = None,
    ) -> list[SearchRow]:
        """Search for similar embeddings using cosine distance.

        Args:
            query_embedding: The query vector to compare against.
            source_type: Optional filter by content type.
            source_ids: Optional set of source UUIDs to restrict search to.
            threshold: Minimum cosine similarity (default 0.7).
            limit: Maximum number of results (default 20).
            model: Optional model filter.
            novel_id: Optional novel scope — restricts results to that
                novel's KB entries and excludes orphaned rows (ADR-088;
                the suggestions path always passes it).

        Returns:
            List of SearchRow objects ordered by similarity descending.
            Each row includes KB entry metadata (usage_count, last_referenced_at)
            for hybrid scoring.
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
