"""Integration tests for EmbeddingRepository — CRUD operations.

Tests require a real PostgreSQL with pgvector extension.
Tests are skipped if pgvector is not available.
"""

from __future__ import annotations

import uuid
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


# Small test vector (dimension must match the column definition)
# Using 1536-dim zero vector for testing
def _make_vector(dim: int = 1536, value: float = 0.01) -> list[float]:
    """Create a simple test vector."""
    return [value] * dim


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


class TestEmbeddingRepositoryCRUD:
    """CRUD operations with real pgvector."""

    async def test_upsert_creates_new_embedding(self, db_session: AsyncSession) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()
        vector = _make_vector()

        result = await repo.upsert(
            source_type="kb_entry",
            source_id=source_id,
            content_hash="hash123",
            embedding=vector,
            model="text-embedding-3-small",
            dimension=1536,
        )

        assert result.id is not None
        assert result.source_type == "kb_entry"
        assert result.source_id == source_id
        assert result.content_hash == "hash123"
        assert result.model == "text-embedding-3-small"
        assert result.generated_at is not None

    async def test_upsert_on_conflict_updates_existing(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()
        vector1 = _make_vector(value=0.1)
        vector2 = _make_vector(value=0.2)

        await repo.upsert(
            "kb_entry",
            source_id,
            "hash1",
            vector1,
            "text-embedding-3-small",
            1536,
        )
        result = await repo.upsert(
            "kb_entry",
            source_id,
            "hash2",
            vector2,
            "text-embedding-3-small",
            1536,
        )

        assert result.content_hash == "hash2"

    async def test_upsert_different_models_coexist(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        r1 = await repo.upsert(
            "kb_entry",
            source_id,
            "hash1",
            _make_vector(),
            "model-a",
            1536,
        )
        r2 = await repo.upsert(
            "kb_entry",
            source_id,
            "hash2",
            _make_vector(),
            "model-b",
            1536,
        )

        assert r1.model == "model-a"
        assert r2.model == "model-b"

    async def test_delete_removes_embedding(self, db_session: AsyncSession) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        await repo.upsert(
            "kb_entry",
            source_id,
            "hash",
            _make_vector(),
            "text-embedding-3-small",
            1536,
        )
        await repo.delete("kb_entry", source_id)

        result = await repo.get_by_source("kb_entry", source_id)
        assert result is None

    async def test_get_by_source_returns_embedding(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        await repo.upsert(
            "kb_entry",
            source_id,
            "hash",
            _make_vector(),
            "text-embedding-3-small",
            1536,
        )
        result = await repo.get_by_source("kb_entry", source_id)

        assert result is not None
        assert result.source_id == source_id

    async def test_get_by_source_with_model_filter(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        await repo.upsert(
            "kb_entry",
            source_id,
            "hash1",
            _make_vector(),
            "model-a",
            1536,
        )
        await repo.upsert(
            "kb_entry",
            source_id,
            "hash2",
            _make_vector(),
            "model-b",
            1536,
        )

        result = await repo.get_by_source("kb_entry", source_id, model="model-a")
        assert result is not None
        assert result.model == "model-a"

    async def test_get_by_source_nonexistent_returns_none(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        result = await repo.get_by_source("kb_entry", uuid.uuid4())
        assert result is None


class TestEmbeddingDeduplication:
    """Content hash deduplication — upsert same source twice."""

    async def test_upsert_same_source_produces_one_row(
        self,
        db_session: AsyncSession,
    ) -> None:
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        _r1 = await repo.upsert(
            "kb_entry",
            source_id,
            "hash1",
            _make_vector(),
            "text-embedding-3-small",
            1536,
        )
        _r2 = await repo.upsert(
            "kb_entry",
            source_id,
            "hash2",
            _make_vector(),
            "text-embedding-3-small",
            1536,
        )

        # Should have updated, not created a new row
        result = await repo.get_by_source("kb_entry", source_id, model="text-embedding-3-small")
        assert result is not None
        assert result.content_hash == "hash2"  # Updated hash
