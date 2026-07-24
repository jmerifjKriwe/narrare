"""Embedding service — business logic.

Orchestrates embedding generation, vector search with hybrid scoring,
and status tracking. Delegates DB operations to the repository and
embedding generation to ``embed_texts()``.

RULE-06: One responsibility — this file has only business logic.
RULE-07: Service depends on repository (DB) and core (embed_texts, scoring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.embeddings.contracts import (
    DEFAULT_EMBEDDING_SEARCH_LIMIT,
    DEFAULT_EMBEDDING_SEARCH_THRESHOLD,
)
from narrare_core.embeddings.hash import compute_content_hash
from narrare_core.embeddings.scoring import ScoredCandidate, ScoringConfig, rank_candidates
from narrare_core.embeddings.store import EmbeddingStats, SearchResult
from narrare_core.llm.embeddings import embed_texts
from narrare_core.settings import get_core_settings
from narrare_core.shared.errors import EmbeddingError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Business logic for embedding operations.

    Implements ``EmbeddingStoreProtocol`` from core.
    """

    def __init__(
        self,
        repo: EmbeddingRepositoryProtocol,
        *,
        model: str | None = None,
        dimension: int | None = None,
        provider: str = "openai",
        scoring_config: ScoringConfig | None = None,
    ) -> None:
        self._repo = repo
        # DEFAULT_EMBEDDING_MODEL is owned by CoreSettings (ADR-071 §3) — read
        # via get_core_settings(), not os.environ.
        self._model = model or get_core_settings().default_embedding_model
        self._dimension = dimension or 1536
        self._provider = provider
        self._scoring_config = scoring_config or ScoringConfig()

    async def generate(
        self,
        source_type: str,
        source_id: UUID,
        content: str,
    ) -> None:
        """Generate and store an embedding for the given content.

        Computes content hash, calls ``embed_texts()``, and upserts
        the embedding via the repository.

        Args:
            source_type: Content type label (e.g. "kb_entry").
            source_id: UUID of the source entity.
            content: Text content to embed.

        Raises:
            EmbeddingError: If generation or storage fails.
        """
        content_hash = compute_content_hash(content)

        try:
            vectors = await embed_texts([content], model=self._model)
        except Exception as exc:
            logger.error(
                "embedding_generation_failed",
                source_type=source_type,
                source_id=str(source_id),
                error=str(exc),
            )
            raise EmbeddingError(f"Embedding generation failed: {exc}") from exc

        if not vectors:
            raise EmbeddingError("Embedding generation returned no vectors")

        vector = vectors[0]

        await self._repo.upsert(
            source_type=source_type,
            source_id=source_id,
            content_hash=content_hash,
            embedding=vector,
            model=self._model,
            dimension=self._dimension,
        )
        logger.info(
            "embedding_generated",
            source_type=source_type,
            source_id=str(source_id),
            model=self._model,
        )

    async def search(
        self,
        query: str,
        *,
        source_type: str | None = None,
        novel_id: UUID | None = None,
        threshold: float = DEFAULT_EMBEDDING_SEARCH_THRESHOLD,
        limit: int = DEFAULT_EMBEDDING_SEARCH_LIMIT,
        model: str | None = None,
        source_ids: set[UUID] | None = None,
        scoring_config: ScoringConfig | None = None,
    ) -> list[SearchResult]:
        """Search for similar content using vector similarity.

        Generates a query embedding, searches the repository, then
        applies hybrid scoring from core.

        Args:
            query: Text to search for.
            source_type: Optional filter by content type.
            novel_id: Optional — limit to entries in this novel.
            threshold: Minimum similarity score.
            limit: Maximum results.
            model: Model to filter on.
            source_ids: Optional set of source UUIDs to restrict search.
            scoring_config: Override scoring weights.

        Returns:
            List of SearchResult sorted by hybrid score descending.

        Raises:
            EmbeddingError: If query embedding generation fails.
        """
        try:
            vectors = await embed_texts([query], model=model or self._model)
        except Exception as exc:
            raise EmbeddingError(f"Query embedding failed: {exc}") from exc

        if not vectors:
            raise EmbeddingError("Query embedding returned no vectors")

        query_vector = vectors[0]

        raw_results = await self._repo.search(
            query_vector,
            source_type=source_type,
            source_ids=source_ids,
            threshold=threshold,
            limit=limit,
            model=model or self._model,
        )

        if not raw_results:
            return []

        # Apply hybrid scoring — metadata wired from kb_entries via LEFT JOIN
        candidates = [
            ScoredCandidate(
                source_id=row.embedding.source_id,
                source_type=row.embedding.source_type,
                similarity=row.similarity,
                usage_count=row.usage_count,
                last_referenced_at=row.last_referenced_at,
                content_hash=row.embedding.content_hash,
            )
            for row in raw_results
        ]

        ranked = rank_candidates(
            candidates,
            config=scoring_config or self._scoring_config,
        )

        return [
            SearchResult(
                source_id=c.source_id,
                source_type=c.source_type,
                score=c.similarity,  # Use similarity score from ranking
                content_hash=c.content_hash,
            )
            for c in ranked
        ]

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
        await self._repo.delete(source_type, source_id)
        logger.info(
            "embedding_deleted",
            source_type=source_type,
            source_id=str(source_id),
        )

    async def get_status(
        self,
        novel_id: UUID,
        source_ids: set[UUID] | None = None,
    ) -> EmbeddingStats:
        """Return embedding statistics for a novel.

        Args:
            novel_id: UUID of the novel.
            source_ids: Set of source entity UUIDs belonging to the novel.

        Returns:
            Aggregate embedding statistics.
        """
        if source_ids is None:
            source_ids = set()

        return await self._repo.get_status("kb_entry", source_ids)

    async def reprocess(
        self,
        novel_id: UUID,
        model: str | None = None,
        source_ids: list[tuple[UUID, str]] | None = None,
    ) -> int:
        """Re-generate embeddings for all content in a novel.

        Queues background tasks for each source entity.

        Args:
            novel_id: UUID of the novel.
            model: Optional model override.
            source_ids: List of (source_id, content) tuples to reprocess.

        Returns:
            Number of tasks queued.
        """
        if not source_ids:
            return 0

        queued = 0
        for source_id, content in source_ids:
            try:
                await self.generate(
                    source_type="kb_entry",
                    source_id=source_id,
                    content=content,
                )
                queued += 1
            except EmbeddingError:
                logger.warning(
                    "reprocess_item_failed",
                    source_id=str(source_id),
                    novel_id=str(novel_id),
                )

        logger.info(
            "reprocess_completed",
            novel_id=str(novel_id),
            queued=queued,
            total=len(source_ids),
        )
        return queued

    @property
    def model(self) -> str:
        """Return the currently active embedding model."""
        return self._model

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        return self._dimension

    @property
    def provider(self) -> str:
        """Return the embedding provider name."""
        return self._provider
