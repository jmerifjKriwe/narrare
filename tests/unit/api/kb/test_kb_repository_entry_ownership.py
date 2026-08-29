"""Unit tests for KBRepository.filter_ids_in_novel — batch entry∈novel probe (W2).

Split from test_kb_repository.py per RULE-04 (both existing repo test
modules are near the test-size limit). Uses the established mock
AsyncSession pattern from those modules.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.kb.repository import KBRepository

_RESULT_ATTRS = ["scalars", "scalar_one_or_none", "scalar_one"]


def _make_result(**kwargs: object) -> MagicMock:
    """Create a MagicMock that mimics SQLAlchemy's Result (sync methods)."""
    result: MagicMock = MagicMock(spec=_RESULT_ATTRS)
    for key, value in kwargs.items():
        setattr(result, key, value)
    return result


def _returning(value: object) -> MagicMock:
    """Callable mock returning *value* — satisfies RULE-TEST-01."""
    return MagicMock(spec=[], return_value=value)


class TestFilterIdsInNovel:
    """Tests for KBRepository.filter_ids_in_novel()."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock AsyncSession for repository testing."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, mock_session: AsyncMock) -> KBRepository:
        """Create a KBRepository with a mocked session."""
        return KBRepository(mock_session)

    async def test_returns_owned_subset_in_one_query(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """Only ids belonging to the novel come back — one execute call."""
        novel_id = uuid4()
        owned = {uuid4(), uuid4()}
        mock_session.execute.return_value = _make_result(scalars=_returning(iter(list(owned))))

        result = await repo.filter_ids_in_novel(novel_id, owned | {uuid4()})

        assert result == owned
        assert mock_session.execute.await_count == 1

    async def test_empty_input_short_circuits_without_query(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """An empty id set never reaches the database (no ``IN ()`` SQL)."""
        result = await repo.filter_ids_in_novel(uuid4(), set())

        assert result == set()
        mock_session.execute.assert_not_awaited()

    async def test_query_filters_on_novel_and_ids(
        self, repo: KBRepository, mock_session: AsyncMock
    ) -> None:
        """The WHERE clause scopes to the novel and the id batch."""
        novel_id = uuid4()
        entry_ids = {uuid4()}
        mock_session.execute.return_value = _make_result(scalars=_returning(iter([])))

        await repo.filter_ids_in_novel(novel_id, entry_ids)

        statement = cast("MagicMock", mock_session.execute).await_args.args[0]
        where_sql = str(statement.compile()).lower()
        assert "novel_id" in where_sql
        assert "kb_entries.id in" in where_sql
