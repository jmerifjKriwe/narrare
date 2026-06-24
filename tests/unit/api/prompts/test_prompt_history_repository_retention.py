"""Unit tests for PromptHistoryRepository — enforce_retention.

Split from test_prompt_history_repository.py per RULE-04.

Covers the enforce_retention method (id-set pruning strategy).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from collections.abc import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.prompts.repository import PromptHistoryRepository

_RESULT_ATTRS = ["scalars", "scalar_one", "scalar_one_or_none"]


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession for repository testing."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock(spec=AsyncSession.add)
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> PromptHistoryRepository:
    return PromptHistoryRepository(mock_session)


def _make_result(**kwargs: object) -> MagicMock:
    """Create a MagicMock that mimics SQLAlchemy's Result.

    The Result returned by session.execute() has synchronous methods
    (.scalars(), .scalar_one_or_none(), etc.), so we use MagicMock, not AsyncMock.
    """
    result: MagicMock = MagicMock(spec=_RESULT_ATTRS)
    for key, value in kwargs.items():
        setattr(result, key, value)
    return result


def _mock_scalars(values: Sequence[object]) -> MagicMock:
    """Create a callable mock for ``.scalars()`` that supports ``.all()`` chaining."""
    scalar_result = MagicMock(spec=["all"])
    scalar_result.all.return_value = values
    return MagicMock(spec=["__call__"], return_value=scalar_result)


def _returning(value: object) -> MagicMock:
    """Callable mock returning *value* — satisfies RULE-TEST-01."""
    return MagicMock(spec=[], return_value=value)


# ---------------------------------------------------------------------------
# enforce_retention — lines 211-237
# ---------------------------------------------------------------------------


class TestEnforceRetention:
    async def test_no_op_when_total_at_or_below_keep(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """enforce_retention returns 0 when total <= keep (no pruning needed)."""
        count_result = _make_result(scalar_one=_returning(3))
        mock_session.execute.return_value = count_result

        deleted = await repo.enforce_retention("pid", "project", keep=5)

        assert deleted == 0
        # execute called once — only the count query
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_not_awaited()

    async def test_no_op_when_exactly_at_keep_limit(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """enforce_retention returns 0 when total == keep."""
        count_result = _make_result(scalar_one=_returning(100))
        mock_session.execute.return_value = count_result

        deleted = await repo.enforce_retention("pid", "project", keep=100)

        assert deleted == 0

    async def test_prunes_old_rows_when_above_keep(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """enforce_retention prunes old rows and returns deleted count when total > keep.

        Simulates: 5 total rows, keep=3 → 2 pruned.
        """
        id1 = uuid.uuid4()
        id2 = uuid.uuid4()
        id3 = uuid.uuid4()

        # First execute call: count = 5
        count_result = _make_result(scalar_one=_returning(5))
        # Second execute call: list of 3 IDs to keep
        keep_result = _make_result(scalars=_mock_scalars([id1, id2, id3]))
        # Third execute call: delete result
        delete_result = MagicMock(spec=[])
        mock_session.execute.side_effect = [count_result, keep_result, delete_result]

        deleted = await repo.enforce_retention("pid", "project", keep=3)

        assert deleted == 2  # total(5) - keep(3)
        assert mock_session.execute.await_count == 3
        mock_session.flush.assert_awaited_once()

    async def test_id_set_approach_excludes_old_ids(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """enforce_retention selects keep newest IDs then deletes NOT IN that set.

        Verifies the approach is deterministic: 10 total, keep=4 → 6 deleted.
        """
        # Create 4 UUIDs for IDs to keep
        keep_ids = [uuid.uuid4() for _ in range(4)]

        count_result = _make_result(scalar_one=_returning(10))
        keep_result = _make_result(scalars=_mock_scalars(keep_ids))
        delete_result = MagicMock(spec=[])
        mock_session.execute.side_effect = [count_result, keep_result, delete_result]

        deleted = await repo.enforce_retention("pid", "project", keep=4)

        assert deleted == 6  # total(10) - keep(4)
        assert mock_session.execute.await_count == 3

    async def test_uses_default_keep_of_100(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """enforce_retention defaults to keep=100 when not provided."""
        count_result = _make_result(scalar_one=_returning(50))
        mock_session.execute.return_value = count_result

        deleted = await repo.enforce_retention("pid", "project")

        assert deleted == 0  # 50 <= 100, no-op
