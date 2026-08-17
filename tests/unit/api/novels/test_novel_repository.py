"""Unit tests for ``NovelRepository`` query wiring (fake session).

The repository is a thin SQLAlchemy wrapper — these tests exercise each
method's query/return path and the create/update/delete bookkeeping
(flush+refresh, setattr loop, session.delete) without a real database.
Mirrors the fake-session pattern in ``tests/unit/api/settings``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from narrare.novels.repository import NovelRepository
from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest
from tests.factories import make_novel
from tests.fakes.fake_db_session import FakeDbSession, FakeResult

if TYPE_CHECKING:
    from narrare.novels.models import Novel


class TestNovelRepositoryGet:
    async def test_get_returns_novel_when_found(self) -> None:
        """get() returns the scalar from the executed query."""
        novel = make_novel()
        session = FakeDbSession([FakeResult(value=novel)])
        repo = NovelRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.get(novel.id)

        assert result is novel

    async def test_get_returns_none_when_missing(self) -> None:
        """get() returns None when the query yields no row."""
        session = FakeDbSession([FakeResult(value=None)])
        repo = NovelRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.get(uuid4())

        assert result is None

    async def test_get_by_id_filters_by_user(self) -> None:
        """get_by_id() returns the novel scoped to (novel_id, user_id)."""
        novel = make_novel()
        session = FakeDbSession([FakeResult(value=novel)])
        repo = NovelRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.get_by_id(novel.id, novel.user_id)

        assert result is novel


class TestNovelRepositoryList:
    async def test_list_by_user_returns_scalar_list(self) -> None:
        """list_by_user() returns the scalars() result as a list."""
        novels = [make_novel(), make_novel()]
        session = FakeDbSession([FakeResult(scalars=novels)])
        repo = NovelRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.list_by_user(uuid4())

        assert result == novels


class TestNovelRepositoryCreate:
    async def test_create_builds_novel_and_flushes(self) -> None:
        """create() constructs a Novel from the request and flushes it."""
        session = FakeDbSession()
        repo = NovelRepository(cast("object", session))  # type: ignore[arg-type]

        request = CreateNovelRequest(
            title="My Novel", author="Me", genre="drama", writing_language="en"
        )
        result = await repo.create(uuid4(), request)

        assert result.title == "My Novel"
        assert result.author == "Me"
        assert result.genre == "drama"
        assert len(session.added) == 1
        assert session.flush_count == 1
        assert session.added[0] in session.refreshed


class TestNovelRepositoryUpdate:
    async def test_update_applies_provided_fields(self) -> None:
        """update() sets only the non-None fields and flushes."""
        novel: Novel = make_novel(title="Old")
        session = FakeDbSession()
        repo = NovelRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.update(novel, UpdateNovelRequest(title="New", genre="horror"))

        assert result.title == "New"
        assert result.genre == "horror"
        assert session.flush_count == 1

    async def test_update_with_empty_request_only_flushes(self) -> None:
        """An empty update still flushes but changes no fields."""
        novel: Novel = make_novel(title="Untouched")
        session = FakeDbSession()
        repo = NovelRepository(cast("object", session))  # type: ignore[arg-type]

        result = await repo.update(novel, UpdateNovelRequest())

        assert result.title == "Untouched"
        assert session.flush_count == 1


class TestNovelRepositoryDelete:
    async def test_delete_delegates_to_session_and_flushes(self) -> None:
        """delete() removes the novel via the session and flushes once."""
        novel = make_novel()
        session = FakeDbSession()
        repo = NovelRepository(cast("object", session))  # type: ignore[arg-type]

        await repo.delete(novel)

        assert session.deleted == [novel]
        assert session.flush_count == 1


class TestNovelRepositorySeriesMembership:
    """update_series_membership()/clear_series_membership() — UPDATE wiring.

    FakeDbSession (used above) does not record executed statements, so
    these statement-only UPDATE methods are exercised against a recording
    mock AsyncSession (pattern: tests/unit/api/test_evidence_repository.py).
    The compiled statement — table, bound values, novel scoping — is the
    only observable output; SQL semantics are proven at integration level.
    Both methods must stay transaction-neutral: no implicit flush/commit
    (the join/leave service owns the transaction).
    """

    async def test_update_series_membership_executes_scoped_update(self) -> None:
        """update_series_membership() binds series columns scoped to the novel."""
        session = AsyncMock(spec=AsyncSession)
        repo = NovelRepository(session=session)
        novel_id, series_id = uuid4(), uuid4()

        await repo.update_series_membership(novel_id, series_id=series_id, series_position=2)

        session.execute.assert_awaited_once()
        stmt = session.execute.call_args[0][0]
        assert stmt.__visit_name__ == "update"
        compiled = stmt.compile()
        assert "UPDATE novels" in str(compiled)
        assert compiled.params["series_id"] == series_id
        assert compiled.params["series_position"] == 2
        assert compiled.params["id_1"] == novel_id
        session.flush.assert_not_awaited()

    async def test_clear_series_membership_nulls_both_columns(self) -> None:
        """clear_series_membership() NULLs series_id and series_position."""
        session = AsyncMock(spec=AsyncSession)
        repo = NovelRepository(session=session)
        novel_id = uuid4()

        await repo.clear_series_membership(novel_id)

        session.execute.assert_awaited_once()
        stmt = session.execute.call_args[0][0]
        assert stmt.__visit_name__ == "update"
        compiled = stmt.compile()
        assert "UPDATE novels" in str(compiled)
        assert compiled.params["series_id"] is None
        assert compiled.params["series_position"] is None
        assert compiled.params["id_1"] == novel_id
        session.flush.assert_not_awaited()
