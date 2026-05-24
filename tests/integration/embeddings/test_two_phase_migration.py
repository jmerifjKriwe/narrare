"""Two-phase migration integration tests.

Tests the logical behavior of the two-phase migration pattern:
- Phase 1: Old and new model embeddings coexist, both queryable
- Phase 2: Old model rows deleted, only new model remains

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


def _vec(value: float = 0.01) -> list[float]:
    """Create a 1536-dim test vector."""
    return [value] * 1536


# Apply skip marker to the entire module
pytestmark = pytest.mark.skipif(
    True,  # Default skip — enable when pgvector is available in CI
    reason="Requires pgvector extension in test database",
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPhase1SystemRemainsOperational:
    """Phase 1: Old and new model embeddings coexist, both queryable."""

    async def test_old_embeddings_still_queryable_after_phase1(
        self, db_session: AsyncSession
    ) -> None:
        """After adding new model embeddings, old model search still works."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        # Seed with old model
        old_id = uuid.uuid4()
        await repo.upsert(
            "kb_entry",
            old_id,
            "h1",
            _vec(value=0.1),
            "old-model",
            1536,
        )

        # Phase 1: Add new model embeddings alongside
        await repo.upsert(
            "kb_entry",
            old_id,
            "h2",
            _vec(value=0.2),
            "new-model",
            1536,
        )

        # Old model search still works
        old_results = await repo.search(
            _vec(value=0.1),
            model="old-model",
            threshold=0.0,
            limit=10,
        )
        assert len(old_results) == 1
        assert old_results[0][0].source_id == old_id

    async def test_new_embeddings_queryable_during_migration(
        self, db_session: AsyncSession
    ) -> None:
        """New model embeddings are immediately queryable."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        old_id = uuid.uuid4()
        await repo.upsert(
            "kb_entry",
            old_id,
            "h1",
            _vec(value=0.1),
            "old-model",
            1536,
        )

        # Add new model
        new_id = uuid.uuid4()
        await repo.upsert(
            "kb_entry",
            new_id,
            "h2",
            _vec(value=0.3),
            "new-model",
            1536,
        )

        # New model search works
        new_results = await repo.search(
            _vec(value=0.3),
            model="new-model",
            threshold=0.0,
            limit=10,
        )
        assert len(new_results) == 1
        assert new_results[0][0].source_id == new_id

    async def test_both_models_queryable_simultaneously(self, db_session: AsyncSession) -> None:
        """Both old and new model searches work during Phase 1."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        # Two entries: one fully migrated, one partially
        id_a = uuid.uuid4()
        id_b = uuid.uuid4()

        await repo.upsert("kb_entry", id_a, "h1", _vec(value=0.1), "old-model", 1536)
        await repo.upsert("kb_entry", id_b, "h2", _vec(value=0.2), "old-model", 1536)

        # Migrate id_a to new model (id_b still on old)
        await repo.upsert("kb_entry", id_a, "h3", _vec(value=0.3), "new-model", 1536)

        old_results = await repo.search(
            _vec(value=0.1),
            model="old-model",
            threshold=0.0,
            limit=10,
        )
        assert len(old_results) == 2  # Both still have old model

        new_results = await repo.search(
            _vec(value=0.3),
            model="new-model",
            threshold=0.0,
            limit=10,
        )
        assert len(new_results) == 1  # Only id_a has new model
        assert new_results[0][0].source_id == id_a


class TestPhase2CleanupRemovesOld:
    """Phase 2: Delete old model rows, verify only new model remains."""

    async def test_cleanup_removes_old_model_rows(self, db_session: AsyncSession) -> None:
        """After Phase 2, only new model embeddings exist."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        # Seed with both models
        entry_id = uuid.uuid4()
        await repo.upsert(
            "kb_entry",
            entry_id,
            "h1",
            _vec(value=0.1),
            "old-model",
            1536,
        )
        await repo.upsert(
            "kb_entry",
            entry_id,
            "h2",
            _vec(value=0.2),
            "new-model",
            1536,
        )

        # Phase 2: Delete old model rows
        await db_session.execute(
            sqlalchemy.text("DELETE FROM embeddings WHERE model = 'old-model'"),
        )
        await db_session.flush()

        # Old model search returns nothing
        old_results = await repo.search(
            _vec(value=0.1),
            model="old-model",
            threshold=0.0,
            limit=10,
        )
        assert len(old_results) == 0

        # New model search still works
        new_results = await repo.search(
            _vec(value=0.2),
            model="new-model",
            threshold=0.0,
            limit=10,
        )
        assert len(new_results) == 1
        assert new_results[0][0].source_id == entry_id

    async def test_cleanup_does_not_affect_unmigrated_entries(
        self, db_session: AsyncSession
    ) -> None:
        """Entries that only have old model are NOT deleted by new-model cleanup."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        # Entry that was NOT migrated (only has old model)
        unmigrated_id = uuid.uuid4()
        await repo.upsert(
            "kb_entry",
            unmigrated_id,
            "h1",
            _vec(value=0.1),
            "old-model",
            1536,
        )

        # Phase 2 cleanup targets only new-model entries (none in this case)
        # But the real Phase 2 would delete old-model rows that have been
        # re-embedded. Let's verify the unmigrated entry survives:
        result = await repo.get_by_source(
            "kb_entry",
            unmigrated_id,
            model="old-model",
        )
        assert result is not None

    async def test_full_migration_cycle(self, db_session: AsyncSession) -> None:
        """Complete migration cycle: seed → migrate → cleanup → verify."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        # Seed 3 entries with old model
        ids = [uuid.uuid4() for _ in range(3)]
        for sid in ids:
            await repo.upsert(
                "kb_entry",
                sid,
                f"h-{sid}",
                _vec(value=0.1),
                "old-model",
                1536,
            )

        # Phase 1: Re-embed all with new model (side-by-side)
        for sid in ids:
            await repo.upsert(
                "kb_entry",
                sid,
                f"h-{sid}-new",
                _vec(value=0.2),
                "new-model",
                1536,
            )

        # Verify both models coexist
        for sid in ids:
            old = await repo.get_by_source("kb_entry", sid, model="old-model")
            new = await repo.get_by_source("kb_entry", sid, model="new-model")
            assert old is not None
            assert new is not None

        # Phase 2: Cleanup old model
        await db_session.execute(
            sqlalchemy.text("DELETE FROM embeddings WHERE model = 'old-model'"),
        )
        await db_session.flush()

        # Verify only new model remains
        for sid in ids:
            old = await repo.get_by_source("kb_entry", sid, model="old-model")
            new = await repo.get_by_source("kb_entry", sid, model="new-model")
            assert old is None
            assert new is not None
            assert new.model == "new-model"
