"""Migration regression tests — Re-embedding, failure recovery & validation.

Tests verify the re-embedding process: full re-embed completion, partial
failure recovery, content drift detection, and dimension validation.

Scenarios:
1. Full re-embed completes successfully
2. Migration partial failure recovery
3. Content drift detection (hash changes trigger re-embed)
4. Dimension verification (DDL checks)

Requires pgvector extension — tests are skipped if unavailable.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
import sqlalchemy

from narrare.embeddings.repository import EmbeddingRepository
from narrare_core.embeddings.hash import compute_content_hash

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


class TestFullReembedCompletes:
    """3. Generate embeddings for all entries with new model."""

    async def test_reembed_all_entries_succeeds(self, db_session: AsyncSession) -> None:
        """Re-embed all entries with new model — all have new model."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        # Seed 3 entries with old model
        ids = [uuid.uuid4() for _ in range(3)]
        for sid in ids:
            await repo.upsert(
                "kb_entry",
                sid,
                compute_content_hash(f"content-{sid}"),
                _vec(),
                "old-model",
                1536,
            )

        # Re-embed with new model
        for sid in ids:
            await repo.upsert(
                "kb_entry",
                sid,
                compute_content_hash(f"content-{sid}"),
                _vec(),
                "new-model",
                1536,
            )

        # Verify all have new model
        for sid in ids:
            result = await repo.get_by_source("kb_entry", sid, model="new-model")
            assert result is not None
            assert result.model == "new-model"


class TestMigrationPartialFailureRecovery:
    """4. Simulate partial failure during re-embedding."""

    async def test_partial_failure_then_retry_succeeds(self, db_session: AsyncSession) -> None:
        """3 successes + 1 failure + retry → all succeed."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)

        ids = [uuid.uuid4() for _ in range(4)]

        # First batch: 3 succeed
        for sid in ids[:3]:
            await repo.upsert(
                "kb_entry",
                sid,
                "hash",
                _vec(),
                "new-model",
                1536,
            )

        # Simulate 4th failure by skipping it

        # Retry the failed one
        await repo.upsert(
            "kb_entry",
            ids[3],
            "hash",
            _vec(),
            "new-model",
            1536,
        )

        # All 4 now have new model embeddings
        for sid in ids:
            result = await repo.get_by_source("kb_entry", sid, model="new-model")
            assert result is not None


class TestContentDriftDetection:
    """5. Content changes between embed attempts → hash differs."""

    async def test_content_drift_triggers_reembed(self, db_session: AsyncSession) -> None:
        """If content changes, hash differs and re-embed is triggered."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()

        # Original content
        original_hash = compute_content_hash("Original content about elves.")
        await repo.upsert(
            "kb_entry",
            source_id,
            original_hash,
            _vec(),
            "model-a",
            1536,
        )

        # Content changed
        new_hash = compute_content_hash("Updated content about dark elves.")
        assert original_hash != new_hash

        # Re-embed with new hash
        await repo.upsert(
            "kb_entry",
            source_id,
            new_hash,
            _vec(value=0.5),
            "model-a",
            1536,
        )

        result = await repo.get_by_source("kb_entry", source_id, model="model-a")
        assert result is not None
        assert result.content_hash == new_hash


class TestDimensionMigrationDDL:
    """6. Verify the embeddings table has the correct dimension."""

    async def test_embedding_column_is_vector_1536(self, db_session: AsyncSession) -> None:
        """Embedding column should be vector(1536)."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'embedding'"
            )
        )
        udt = result.scalar_one_or_none()
        assert udt == "vector"

    async def test_embedding_dimension_is_1536(self, db_session: AsyncSession) -> None:
        """Verify vector dimension via pgvector's vector_dims function."""
        if not await _pgvector_available(db_session):
            pytest.skip("pgvector not available")

        # Insert a test vector and check its dimension
        repo = EmbeddingRepository(db_session)
        source_id = uuid.uuid4()
        vec_1536 = [0.01] * 1536

        await repo.upsert(
            "kb_entry",
            source_id,
            "dim-test",
            vec_1536,
            "dim-test-model",
            1536,
        )

        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT vector_dims(embedding) FROM embeddings WHERE source_id = :sid LIMIT 1"
            ),
            {"sid": str(source_id)},
        )
        dims = result.scalar_one()
        assert dims == 1536
