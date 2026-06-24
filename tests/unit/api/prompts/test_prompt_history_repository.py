"""Unit tests for PromptHistoryRepository — mock session tests.

These tests use mock AsyncSession objects to verify repository method behaviors
without requiring a real database. They follow the same pattern as
``tests/unit/api/chapters/test_chapter_repository.py``.

Target uncovered lines:
  - repository.py:56-68  — insert_revision (construction + flush)
  - repository.py:89-100 — list_revisions (ordering + pagination)
  - repository.py:111-113 — get_revision (PK lookup)
  - repository.py:132-142 — get_latest_revision (LIMIT 1)
  - repository.py:154-163 — count (scalar aggregate)
  - repository.py:177-186 — delete_history (count + delete + flush)
  - repository.py:211-237 — enforce_retention (id-set pruning)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

if TYPE_CHECKING:
    from collections.abc import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.prompts.models import PromptRevision
from narrare.prompts.repository import PromptHistoryRepository

_RESULT_ATTRS = ["scalars", "scalar_one", "scalar_one_or_none"]


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock AsyncSession for repository testing.

    The session's execute() returns a MagicMock (not AsyncMock) because
    the Result object returned by execute() has synchronous methods like
    .scalars(), .scalar_one(), and .scalar_one_or_none().
    """
    session = AsyncMock()
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


def _returning(value: object) -> MagicMock:
    """Callable mock returning *value* — satisfies RULE-TEST-01."""
    return MagicMock(spec=[], return_value=value)


def _mock_scalars(values: Sequence[object]) -> MagicMock:
    """Create a callable mock for ``.scalars()`` that supports ``.all()`` chaining.

    The prompt history repository calls ``result.scalars().all()``, which differs
    from the chapter repository's ``list(result.scalars())`` pattern.  This helper
    returns a mock ``scalars`` callable that returns a ``ScalarResult``-like mock
    whose ``.all()`` yields *values*.
    """
    scalar_result = MagicMock(spec=["all"])
    scalar_result.all.return_value = values
    return MagicMock(spec=["__call__"], return_value=scalar_result)


# ---------------------------------------------------------------------------
# insert_revision — lines 56-68
# ---------------------------------------------------------------------------


class TestInsertRevision:
    async def test_creates_revision_with_all_fields(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """insert_revision creates a PromptRevision, adds to session, and flushes."""
        prompt_id = "writing/en/new_chapter"
        scope = "project"
        content = "my override content"
        content_hash = "abc123hash"
        actor_id = uuid.uuid4()
        source = "save"
        change_reason = "tweaked tone"
        restored_from_id = uuid.uuid4()

        result = await repo.insert_revision(
            prompt_id=prompt_id,
            scope=scope,
            content=content,
            content_hash=content_hash,
            actor_id=actor_id,
            source=source,
            change_reason=change_reason,
            restored_from_id=restored_from_id,
        )

        # Verify the PromptRevision was constructed with correct attributes
        mock_session.add.assert_called_once()
        added_revision = mock_session.add.call_args[0][0]
        assert isinstance(added_revision, PromptRevision)
        assert added_revision.prompt_id == prompt_id
        assert added_revision.scope == scope
        assert added_revision.content == content
        assert added_revision.content_hash == content_hash
        assert added_revision.actor_id == actor_id
        assert added_revision.source == source
        assert added_revision.change_reason == change_reason
        assert added_revision.restored_from_id == restored_from_id

        # Verify flush + refresh was called
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(added_revision)

        # Verify the returned revision is the same object
        assert result is added_revision

    async def test_creates_revision_without_optional_fields(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """insert_revision works when change_reason and restored_from_id are None."""
        prompt_id = "writing/en/default"
        scope = "user"
        content = "minimal content"
        content_hash = "def456hash"
        actor_id = uuid.uuid4()
        source = "restore"

        result = await repo.insert_revision(
            prompt_id=prompt_id,
            scope=scope,
            content=content,
            content_hash=content_hash,
            actor_id=actor_id,
            source=source,
        )

        added_revision = mock_session.add.call_args[0][0]
        assert added_revision.change_reason is None
        assert added_revision.restored_from_id is None
        assert result is added_revision

    async def test_creates_revision_with_none_actor(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """insert_revision works when actor_id is None (system saves)."""
        inserted = await repo.insert_revision(
            prompt_id="writing/en/system",
            scope="project",
            content="system save",
            content_hash="syshash",
            actor_id=None,
            source="save",
        )

        added_revision = mock_session.add.call_args[0][0]
        assert inserted is added_revision
        assert added_revision.actor_id is None


# ---------------------------------------------------------------------------
# list_revisions — lines 89-100
# ---------------------------------------------------------------------------


class TestListRevisions:
    async def test_returns_revisions_ordered_by_created_at_desc(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """list_revisions returns list ordered by created_at descending."""
        rev1 = MagicMock(spec=PromptRevision)
        rev2 = MagicMock(spec=PromptRevision)
        result = _make_result(scalars=_mock_scalars([rev2, rev1]))
        mock_session.execute.return_value = result

        prompt_id = "writing/en/test"
        revisions = await repo.list_revisions(prompt_id, "project", limit=50, offset=0)

        assert len(revisions) == 2
        assert revisions[0] is rev2
        assert revisions[1] is rev1
        mock_session.execute.assert_called_once()

    async def test_respects_limit_and_offset(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """list_revisions passes limit and offset to the query."""
        rev = MagicMock(spec=PromptRevision)
        result = _make_result(scalars=_mock_scalars([rev]))
        mock_session.execute.return_value = result

        revisions = await repo.list_revisions("pid", "scope", limit=10, offset=5)

        assert len(revisions) == 1
        # Verify execute was called — we can't easily inspect SQLAlchemy stmt args
        # but we can verify the method didn't error and returned correct data
        mock_session.execute.assert_called_once()

    async def test_returns_empty_list_when_no_revisions(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """list_revisions returns empty list when no revisions exist."""
        result = _make_result(scalars=_mock_scalars([]))
        mock_session.execute.return_value = result

        revisions = await repo.list_revisions("pid", "scope", limit=50, offset=0)

        assert revisions == []


# ---------------------------------------------------------------------------
# get_revision — lines 111-113
# ---------------------------------------------------------------------------


class TestGetRevision:
    async def test_returns_revision_when_found(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """get_revision returns the revision when the UUID exists."""
        revision = MagicMock(spec=PromptRevision)
        result = _make_result(scalar_one_or_none=_returning(revision))
        mock_session.execute.return_value = result

        revision_id = uuid.uuid4()
        found = await repo.get_revision(revision_id)

        assert found is revision
        mock_session.execute.assert_called_once()

    async def test_returns_none_when_not_found(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """get_revision returns None when the UUID is not found."""
        result = _make_result(scalar_one_or_none=_returning(None))
        mock_session.execute.return_value = result

        found = await repo.get_revision(uuid.uuid4())

        assert found is None


# ---------------------------------------------------------------------------
# get_latest_revision — lines 132-142
# ---------------------------------------------------------------------------


class TestGetLatestRevision:
    async def test_returns_newest_revision(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """get_latest_revision returns the most recent revision (LIMIT 1)."""
        latest = MagicMock(spec=PromptRevision)
        result = _make_result(scalar_one_or_none=_returning(latest))
        mock_session.execute.return_value = result

        found = await repo.get_latest_revision("pid", "project")

        assert found is latest
        mock_session.execute.assert_called_once()

    async def test_returns_none_when_no_history(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """get_latest_revision returns None when no revisions exist."""
        result = _make_result(scalar_one_or_none=_returning(None))
        mock_session.execute.return_value = result

        found = await repo.get_latest_revision("pid", "project")

        assert found is None


# ---------------------------------------------------------------------------
# count — lines 154-163
# ---------------------------------------------------------------------------


class TestCount:
    async def test_returns_count_of_matching_rows(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """count returns the integer row count for matching prompt_id + scope."""
        result = _make_result(scalar_one=_returning(5))
        mock_session.execute.return_value = result

        count = await repo.count("pid", "project")

        assert count == 5
        mock_session.execute.assert_called_once()

    async def test_returns_zero_when_no_matching_rows(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """count returns 0 when no matching rows exist."""
        result = _make_result(scalar_one=_returning(0))
        mock_session.execute.return_value = result

        count = await repo.count("pid", "project")

        assert count == 0


# ---------------------------------------------------------------------------
# delete_history — lines 177-186
# ---------------------------------------------------------------------------


class TestDeleteHistory:
    async def test_returns_zero_when_no_history(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """delete_history returns 0 when count() returns 0 (no rows to delete)."""
        count_result = _make_result(scalar_one=_returning(0))
        mock_session.execute.return_value = count_result

        deleted = await repo.delete_history("pid", "project")

        assert deleted == 0
        # execute should be called exactly once (only the count query)
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_not_awaited()

    async def test_deletes_rows_and_returns_count(
        self, repo: PromptHistoryRepository, mock_session: AsyncMock
    ) -> None:
        """delete_history deletes matching rows and returns the count."""
        # First call to execute() returns count, second returns delete result
        count_result = _make_result(scalar_one=_returning(3))
        delete_result = MagicMock(spec=[])
        mock_session.execute.side_effect = [count_result, delete_result]

        deleted = await repo.delete_history("pid", "project")

        assert deleted == 3
        # execute should be called twice (count + delete)
        assert mock_session.execute.await_count == 2
        # flush should be called after delete
        mock_session.flush.assert_awaited_once()
