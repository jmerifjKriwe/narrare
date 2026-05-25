"""Migration regression tests — Model coexistence & rollback safety.

Tests verify side-by-side model coexistence, search continuity during
migration, and rollback safety. Since we can't change pgvector dimensions
in tests, these test the repository's filtering, coexistence, and cleanup
behavior.

Scenarios:
1. Side-by-side coexistence (different models for same source)
2. Search continuity during migration (mixed old/new model results)
3. Migration rollback safety (old model still works after new model cleanup)

Requires pgvector extension — tests are skipped if unavailable.
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
# Helpers
# ---------------------------------------------------------------------------


async def _pgvector_available(session: AsyncSession) -> bool:
    """Check if the pgvector extension is installed."""
    result = await session.execute(
        sqlalchemy.text("SELECT * FROM pg_extension WHERE extname = 'vector'")
    )
    return result.fetchone() is not None


def _vec(dim: int = 1536, value: float = 0.01) -> list[float]:
    """Create a test vector of given dimension."""
    return [value] * dim


# Apply skip marker to the entire module
pytestmark = pytest.mark.skipif(
    True,  # Default skip — enable when pgvector is available in CI
    reason="Requires pgvector extension in test database",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSideBySideCoexistence:
    """1. Embeddings with different models coexist for same source."""

    async def test_different_models_coexist_for_same_source(self, db_session: AsyncSession) -> None:
        """Insert embeddings with model='small' and model='large', verify both exist."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        await repo.upsert("kb_entry", source_id, "hash1", _vec(), "text-embedding-3-small", 1536)
        await repo.upsert("kb_entry", source_id, "hash2", _vec(), "text-embedding-3-large", 1536)

        small = await repo.get_by_source("kb_entry", source_id, model="text-embedding-3-small")
        large = await repo.get_by_source("kb_entry", source_id, model="text-embedding-3-large")

        assert small is not None
        assert small.model == "text-embedding-3-small"
        assert large is not None
        assert large.model == "text-embedding-3-large"

    async def test_search_filters_by_model(self, db_session: AsyncSession) -> None:
        """Search with model filter only returns that model's embeddings."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        await repo.upsert("kb_entry", source_id, "h1", _vec(), "old-model", 1536)
        await repo.upsert("kb_entry", source_id, "h2", _vec(), "new-model", 1536)

        results = await repo.search(
            _vec(),
            model="new-model",
            threshold=0.0,
            limit=10,
        )

        assert len(results) == 1
        assert results[0][0].model == "new-model"


class TestSearchContinuityDuringMigration:
    """2. Search works with mixed old/new model embeddings."""

    async def test_search_finds_only_new_model_entries(self, db_session: AsyncSession) -> None:
        """Some entries have new model, some old — search finds only new."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        # Old model entries
        await repo.upsert("kb_entry", uuid.uuid4(), "h1", _vec(value=0.1), "old-model", 1536)
        await repo.upsert("kb_entry", uuid.uuid4(), "h2", _vec(value=0.2), "old-model", 1536)

        # New model entries
        new_id = uuid.uuid4()
        await repo.upsert("kb_entry", new_id, "h3", _vec(value=0.3), "new-model", 1536)

        results = await repo.search(
            _vec(value=0.3),
            model="new-model",
            threshold=0.0,
            limit=10,
        )

        assert len(results) == 1
        assert results[0][0].source_id == new_id


class TestMigrationRollbackSafety:
    """7. Insert data, simulate rollback, verify old model still works."""

    async def test_rollback_new_model_old_still_works(self, db_session: AsyncSession) -> None:
        """After deleting new-model rows, old model search still works."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        old_id = uuid.uuid4()
        new_id = uuid.uuid4()

        # Old model entries
        await repo.upsert(
            "kb_entry",
            old_id,
            "h1",
            _vec(value=0.1),
            "old-model",
            1536,
        )

        # New model entries (added during migration)
        await repo.upsert(
            "kb_entry",
            new_id,
            "h2",
            _vec(value=0.2),
            "new-model",
            1536,
        )

        # Simulate rollback: delete new model entries
        await db_session.execute(
            sqlalchemy.text("DELETE FROM embeddings WHERE model = 'new-model'"),
        )
        await db_session.flush()

        # Old model search still works
        results = await repo.search(
            _vec(value=0.1),
            model="old-model",
            threshold=0.0,
            limit=10,
        )
        assert len(results) == 1
        assert results[0][0].source_id == old_id
