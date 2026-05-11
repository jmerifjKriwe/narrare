"""Unit tests for novels/repository.py — DB query layer."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.novels.models import Novel
from narrare.novels.repository import NovelRepository
from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest


def _make_novel(**kwargs: object) -> Novel:
    from sqlalchemy.orm.attributes import set_attribute

    novel = Novel()
    set_attribute(novel, "id", kwargs.get("id", uuid.uuid4()))
    set_attribute(novel, "user_id", kwargs.get("user_id", uuid.uuid4()))
    set_attribute(novel, "title", kwargs.get("title", "Test Novel"))
    set_attribute(novel, "author", kwargs.get("author", "Author"))
    set_attribute(novel, "genre", kwargs.get("genre", ""))
    set_attribute(novel, "language", kwargs.get("language", "en"))
    set_attribute(novel, "tone", kwargs.get("tone", ""))
    set_attribute(novel, "story_structure", kwargs.get("story_structure", "three_act"))
    set_attribute(novel, "logline", kwargs.get("logline", ""))
    set_attribute(novel, "synopsis", kwargs.get("synopsis", ""))
    set_attribute(novel, "is_demo", kwargs.get("is_demo", False))
    return novel


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(mock_session: MagicMock) -> NovelRepository:
    return NovelRepository(mock_session)


class TestNovelRepositoryGetById:
    async def test_returns_novel_when_found(
        self, repo: NovelRepository, mock_session: MagicMock
    ) -> None:
        novel = _make_novel()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = novel
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(novel.id, novel.user_id)

        assert result == novel

    async def test_returns_none_when_not_found(
        self, repo: NovelRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(uuid.uuid4(), uuid.uuid4())

        assert result is None


class TestNovelRepositoryListByUser:
    async def test_returns_novels_ordered_by_updated_at(
        self, repo: NovelRepository, mock_session: MagicMock
    ) -> None:
        novels = [_make_novel(), _make_novel()]
        mock_result = MagicMock()
        mock_result.scalars.return_value = novels
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(uuid.uuid4())

        assert len(result) == 2

    async def test_returns_empty_list_for_no_novels(
        self, repo: NovelRepository, mock_session: MagicMock
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.list_by_user(uuid.uuid4())

        assert result == []


class TestNovelRepositoryCreate:
    async def test_creates_and_flushes_novel(
        self, repo: NovelRepository, mock_session: MagicMock
    ) -> None:
        uid = uuid.uuid4()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        request = CreateNovelRequest(title="New Novel", language="de", genre="fantasy")
        result = await repo.create(uid, request)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.title == "New Novel"
        assert result.user_id == uid


class TestNovelRepositoryUpdate:
    async def test_updates_provided_fields_only(
        self, repo: NovelRepository, mock_session: MagicMock
    ) -> None:
        novel = _make_novel(title="Original")
        mock_session.flush = AsyncMock()

        request = UpdateNovelRequest(title="Updated")
        result = await repo.update(novel, request)

        assert result.title == "Updated"
        mock_session.flush.assert_called_once()

    async def test_update_with_no_fields_keeps_original(
        self, repo: NovelRepository, mock_session: MagicMock
    ) -> None:
        novel = _make_novel(title="Original")
        mock_session.flush = AsyncMock()

        request = UpdateNovelRequest()
        result = await repo.update(novel, request)

        assert result.title == "Original"


class TestNovelRepositoryDelete:
    async def test_deletes_novel_and_flushes(
        self, repo: NovelRepository, mock_session: MagicMock
    ) -> None:
        novel = _make_novel()
        mock_session.delete = AsyncMock()
        mock_session.flush = AsyncMock()

        await repo.delete(novel)

        mock_session.delete.assert_called_once_with(novel)
        mock_session.flush.assert_called_once()
