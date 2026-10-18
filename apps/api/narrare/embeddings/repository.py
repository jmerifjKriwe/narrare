"""Embedding repository — DB queries only.

Handles persistence of ``Embedding`` rows using raw SQL for pgvector
compatibility. No business logic — only CRUD + vector search.

Uses raw ``sqlalchemy.text()`` for INSERT/SELECT with pgvector operators
(``<=>`` cosine distance) because the ORM doesn't natively support them.

Query building is delegated to ``search_queries`` module for RULE-04
compliance.

RULE-06: One responsibility per file — this file has only DB queries.
RULE-08: pgvector operations confined to the embeddings module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import sqlalchemy
import structlog

from narrare._app.base_repository import BaseRepository
from narrare.embeddings.contracts import (
    DEFAULT_EMBEDDING_SEARCH_LIMIT,
    DEFAULT_EMBEDDING_SEARCH_THRESHOLD,
)

if TYPE_CHECKING:
    from narrare.embeddings.models import Embedding

from narrare.embeddings.search_queries import (
    SearchRow,
    build_batch_upsert_query,
    build_get_by_source_query,
    build_search_query,
    build_vector_str,
    parse_embedding_row,
    parse_search_row,
)
from narrare_core.embeddings.store import EmbeddingStats

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)


class EmbeddingRepository(BaseRepository):
    """Persistence operations for embeddings with pgvector support."""

    async def upsert(
        self,
        source_type: str,
        source_id: UUID,
        content_hash: str,
        embedding: list[float],
        model: str,
        dimension: int,
    ) -> Embedding:
        """Insert or update an embedding row using raw SQL.

        Uses ``INSERT ... ON CONFLICT ... DO UPDATE`` for idempotent writes.
        The ``embedding`` vector is passed as a string literal for pgvector.
        """
        vec_str = build_vector_str(embedding)
        result = await self._session.execute(
            sqlalchemy.text(
                """
                INSERT INTO embeddings
                    (id, source_type, source_id, content_hash,
                     embedding, model, dimension, generated_at)
                VALUES
                    (gen_random_uuid(), :source_type, :source_id, :content_hash,
                     CAST(:embedding AS vector), :model, :dimension, now())
                ON CONFLICT (source_type, source_id, model)
                    DO UPDATE SET
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        dimension = EXCLUDED.dimension,
                        generated_at = now()
                RETURNING id, source_type, source_id, content_hash,
                          embedding, model, dimension, generated_at
                """
            ),
            {
                "source_type": source_type,
                "source_id": str(source_id),
                "content_hash": content_hash,
                "embedding": vec_str,
                "model": model,
                "dimension": dimension,
            },
        )
        row = result.fetchone()
        await self._session.flush()

        # RETURNING guarantees a row from INSERT ON CONFLICT
        assert row is not None
        return parse_embedding_row(cast("tuple[object, ...]", row))

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

        Returns ``SearchRow`` objects ordered by similarity descending.
        Only results above ``threshold`` are returned. Each row includes
        KB entry metadata (usage_count, last_referenced_at) via LEFT JOIN.

        ``novel_id`` scopes the results to one novel's KB entries (the
        suggestions contract — ADR-088); when set, orphaned embedding
        rows and other source_types are excluded.
        """
        vec_str = build_vector_str(query_embedding)
        sql, params = build_search_query(
            vec_str,
            source_type=source_type,
            source_ids=source_ids,
            threshold=threshold,
            limit=limit,
            model=model,
            novel_id=novel_id,
        )
        result = await self._session.execute(sql, params)

        rows = result.fetchall()
        return [parse_search_row(cast("tuple[object, ...]", row)) for row in rows]

    async def delete(
        self,
        source_type: str,
        source_id: UUID,
    ) -> None:
        """Delete all embeddings for a source entity."""
        await self._session.execute(
            sqlalchemy.text(
                "DELETE FROM embeddings WHERE source_type = :source_type AND source_id = :source_id"
            ),
            {"source_type": source_type, "source_id": str(source_id)},
        )
        await self._session.flush()

    async def get_by_source(
        self,
        source_type: str,
        source_id: UUID,
        model: str | None = None,
    ) -> Embedding | None:
        """Fetch an embedding by source identity."""
        sql, params = build_get_by_source_query(source_type, source_id, model)
        result = await self._session.execute(sql, params)
        row = result.fetchone()
        if row is None:
            return None

        return parse_embedding_row(cast("tuple[object, ...]", row))

    async def get_status(
        self,
        source_type: str,
        source_ids: set[UUID],
    ) -> EmbeddingStats:
        """Compute embedding statistics for a set of source entities.

        Counts total (len of source_ids), embedded (those with embeddings),
        and derives pending/failed from the difference.
        """
        total = len(source_ids)

        if total == 0:
            return EmbeddingStats(
                total=0,
                embedded=0,
                pending=0,
                failed=0,
                coverage_percentage=0.0,
            )

        id_strs = [str(sid) for sid in source_ids]
        result = await self._session.execute(
            sqlalchemy.text(
                """
                SELECT COUNT(DISTINCT source_id) AS embedded_count
                FROM embeddings
                WHERE source_type = :source_type
                  AND source_id = ANY(:source_ids)
                """
            ),
            {"source_type": source_type, "source_ids": id_strs},
        )
        row = result.fetchone()
        embedded = int(row[0]) if row else 0

        pending = total - embedded
        failed = 0  # No failed tracking in current schema — all non-embedded are pending

        coverage = round((embedded / total) * 100.0, 1) if total > 0 else 0.0

        return EmbeddingStats(
            total=total,
            embedded=embedded,
            pending=pending,
            failed=failed,
            coverage_percentage=coverage,
        )

    async def batch_upsert(
        self,
        items: list[tuple[str, UUID, str, list[float], str, int]],
    ) -> int:
        """Insert or update multiple embedding rows in a single query.

        Each item is: (source_type, source_id, content_hash, embedding, model, dimension).
        """
        if not items:
            return 0

        sql, params = build_batch_upsert_query(items)

        await self._session.execute(sql, params)
        await self._session.flush()
        return len(items)
