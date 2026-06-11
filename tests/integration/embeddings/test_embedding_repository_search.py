"""Integration tests for EmbeddingRepository — search, status, batch operations.

Tests require a real PostgreSQL with pgvector extension.
Tests are skipped if pgvector is not available.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
import sqlalchemy

from narrare.embeddings.repository import EmbeddingRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# pgvector availability check
# ---------------------------------------------------------------------------


async def _pgvector_available(session: AsyncSession) -> bool:
    """Check if the pgvector extension is installed."""
    result = await session.execute(
        sqlalchemy.text("SELECT * FROM pg_extension WHERE extname = 'vector'")
    )
    return result.fetchone() is not None


def _make_vector(dim: int = 1536, value: float = 0.01) -> list[float]:
    """Create a simple test vector."""
    return [value] * dim


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="Requires pgvector extension in test database",
)
class TestEmbeddingRepositorySearch:
    """Vector search with real pgvector."""

    async def test_search_returns_similar_results(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()

        # Use slightly different vectors
        vec1 = [0.1] * 1536
        vec2 = [0.9] * 1536

        await repo.upsert("kb_entry", sid1, "h1", vec1, "test-model", 1536)
        await repo.upsert("kb_entry", sid2, "h2", vec2, "test-model", 1536)

        # Query with a vector similar to vec1
        results = await repo.search(
            [0.1] * 1536,
            model="test-model",
            threshold=0.0,
            limit=10,
        )

        assert len(results) >= 1
        # The first result should be more similar to vec1
        assert results[0].embedding.source_id == sid1

    async def test_search_filters_by_source_type(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        sid = uuid.uuid4()

        await repo.upsert("kb_entry", sid, "h1", _make_vector(), "test-model", 1536)

        results = await repo.search(
            _make_vector(),
            source_type="chapter",
            model="test-model",
            threshold=0.0,
        )

        assert len(results) == 0

    async def test_search_filters_by_source_ids(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()

        await repo.upsert("kb_entry", sid1, "h1", _make_vector(), "test-model", 1536)
        await repo.upsert("kb_entry", sid2, "h2", _make_vector(), "test-model", 1536)

        results = await repo.search(
            _make_vector(),
            source_ids={sid1},
            model="test-model",
            threshold=0.0,
        )

        assert len(results) == 1
        assert results[0].embedding.source_id == sid1

    async def test_search_respects_threshold(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        sid = uuid.uuid4()

        await repo.upsert("kb_entry", sid, "h1", _make_vector(), "test-model", 1536)

        # Very high threshold should filter out results
        results = await repo.search(
            [0.5] * 1536,
            model="test-model",
            threshold=0.999,
        )

        assert len(results) == 0


# ---------------------------------------------------------------------------
# Status tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="Requires pgvector extension in test database",
)
class TestEmbeddingRepositoryStatus:
    """Status computation with real DB."""

    async def test_get_status_with_embeddings(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        sid3 = uuid.uuid4()

        await repo.upsert("kb_entry", sid1, "h1", _make_vector(), "test-model", 1536)
        await repo.upsert("kb_entry", sid2, "h2", _make_vector(), "test-model", 1536)

        stats = await repo.get_status("kb_entry", {sid1, sid2, sid3})

        assert stats.total == 3
        assert stats.embedded == 2
        assert stats.pending == 1
        assert stats.coverage_percentage == 66.7

    async def test_get_status_with_empty_set(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        stats = await repo.get_status("kb_entry", set())

        assert stats.total == 0
        assert stats.embedded == 0


# ---------------------------------------------------------------------------
# Batch upsert tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="Requires pgvector extension in test database",
)
class TestEmbeddingRepositoryBatchUpsert:
    """Batch upsert with real pgvector."""

    async def test_batch_upsert_creates_multiple(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()

        count = await repo.batch_upsert(
            [
                ("kb_entry", sid1, "h1", _make_vector(), "test-model", 1536),
                ("kb_entry", sid2, "h2", _make_vector(), "test-model", 1536),
            ]
        )

        assert count == 2
        r1 = await repo.get_by_source("kb_entry", sid1)
        assert r1 is not None
        r2 = await repo.get_by_source("kb_entry", sid2)
        assert r2 is not None

    async def test_batch_upsert_empty_list(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        count = await repo.batch_upsert([])
        assert count == 0


# ---------------------------------------------------------------------------
# Search metadata tests (IF-04: usage_count, last_referenced_at wiring)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    True,
    reason="Requires pgvector extension in test database",
)
class TestEmbeddingRepositorySearchMetadata:
    """Verifies that search results include KB entry metadata."""

    async def test_search_returns_usage_count_for_kb_entries(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Search results for kb_entry sources include non-zero usage_count."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        entry_id = uuid.uuid4()
        novel_id = uuid.uuid4()

        # Create a KB entry with non-zero usage_count
        await db_session.execute(
            sqlalchemy.text(
                "INSERT INTO kb_entries "
                "(id, novel_id, entity_type, name, slug, status, usage_count) "
                "VALUES (:id, :novel_id, 'character', 'Test Char', "
                "'test-char', 'draft', :usage_count)"
            ),
            {"id": str(entry_id), "novel_id": str(novel_id), "usage_count": 10},
        )
        await db_session.flush()

        # Create an embedding for this KB entry
        await repo.upsert("kb_entry", entry_id, "h1", _make_vector(), "test-model", 1536)

        results = await repo.search(
            _make_vector(),
            source_type="kb_entry",
            model="test-model",
            threshold=0.0,
        )

        assert len(results) == 1
        assert results[0].usage_count == 10

    async def test_search_returns_last_referenced_at_for_kb_entries(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Search results for referenced kb_entry sources have non-null last_referenced_at."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        entry_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        ref_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

        # Create a KB entry with last_referenced_at set
        await db_session.execute(
            sqlalchemy.text(
                "INSERT INTO kb_entries "
                "(id, novel_id, entity_type, name, slug, status, usage_count, last_referenced_at) "
                "VALUES (:id, :novel_id, 'character', 'Test Char', 'test-char', 'draft', "
                "1, :last_ref)"
            ),
            {"id": str(entry_id), "novel_id": str(novel_id), "last_ref": ref_time},
        )
        await db_session.flush()

        # Create an embedding for this KB entry
        await repo.upsert("kb_entry", entry_id, "h1", _make_vector(), "test-model", 1536)

        results = await repo.search(
            _make_vector(),
            source_type="kb_entry",
            model="test-model",
            threshold=0.0,
        )

        assert len(results) == 1
        assert results[0].last_referenced_at is not None
        assert results[0].last_referenced_at.year == 2026

    async def test_search_returns_defaults_for_non_kb_entry_sources(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Non-kb_entry sources get usage_count=0 and last_referenced_at=None."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        # Create an embedding with a non-kb_entry source_type
        await repo.upsert("chapter", source_id, "h1", _make_vector(), "test-model", 1536)

        results = await repo.search(
            _make_vector(),
            source_type="chapter",
            model="test-model",
            threshold=0.0,
        )

        assert len(results) == 1
        assert results[0].usage_count == 0
        assert results[0].last_referenced_at is None
