"""Unit tests for ``EmbeddingRepository`` boundary branches.

The repository uses raw SQL against a live session, so most methods are
exercised at integration level. These unit tests cover the pure-logic early
returns (empty inputs) and the count-computation branch, which need no DB —
``self._session`` is mocked with ``spec=AsyncSession`` (RULE-TEST-01).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.embeddings.repository import EmbeddingRepository
from narrare_core.embeddings.store import EmbeddingStats


class _FakeResult:
    """Minimal stand-in for a SQLAlchemy ``Result`` (fetchone/fetchall)."""

    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row

    def fetchall(self) -> list[tuple[object, ...]]:
        return [self._row] if self._row is not None else []


def _make_repo() -> tuple[EmbeddingRepository, MagicMock]:
    """Return a repository backed by a mocked async session."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return EmbeddingRepository(session), session


class TestGetStatus:
    async def test_empty_source_ids_returns_zero_stats_without_db(self) -> None:
        repo, session = _make_repo()

        stats = await repo.get_status("kb_entry", set())

        assert isinstance(stats, EmbeddingStats)
        assert stats.total == 0
        assert stats.embedded == 0
        assert stats.pending == 0
        assert stats.failed == 0
        assert stats.coverage_percentage == 0.0
        # Empty input short-circuits before any query is issued.
        session.execute.assert_not_called()

    async def test_computes_coverage_from_embedded_count(self) -> None:
        repo, session = _make_repo()
        session.execute.return_value = _FakeResult(row=(3,))

        source_ids = {uuid4() for _ in range(5)}
        stats = await repo.get_status("kb_entry", source_ids)

        assert stats.total == 5
        assert stats.embedded == 3
        assert stats.pending == 2
        assert stats.failed == 0
        assert stats.coverage_percentage == 60.0

    async def test_zero_embedded_yields_zero_coverage(self) -> None:
        repo, session = _make_repo()
        session.execute.return_value = _FakeResult(row=(0,))

        stats = await repo.get_status("kb_entry", {uuid4(), uuid4()})

        assert stats.embedded == 0
        assert stats.pending == 2
        assert stats.coverage_percentage == 0.0


class TestBatchUpsert:
    async def test_empty_items_returns_zero_without_db(self) -> None:
        repo, session = _make_repo()

        assert await repo.batch_upsert([]) == 0
        session.execute.assert_not_called()


class TestGetBySource:
    async def test_missing_row_returns_none(self) -> None:
        repo, session = _make_repo()
        session.execute.return_value = _FakeResult(row=None)

        assert await repo.get_by_source("kb_entry", uuid4()) is None
