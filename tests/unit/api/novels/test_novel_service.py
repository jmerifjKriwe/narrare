"""Unit tests for novels/service.py — business logic."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from narrare.novels.models import Novel
from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest
from narrare.novels.service import NovelService


def _make_novel(**kwargs: Any) -> Novel:  # pyright: ignore[reportArgumentType]
    from sqlalchemy.orm.attributes import set_attribute

    novel: Novel = Novel()
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
def service(mock_session: MagicMock) -> NovelService:
    svc = NovelService(mock_session)
    return svc


def _create_request(**overrides: str) -> CreateNovelRequest:
    return CreateNovelRequest(title="My Novel", **overrides)  # type: ignore[arg-type]


class TestNovelServiceGet:
    async def test_get_returns_novel_when_found(self, service: NovelService) -> None:
        uid = uuid.uuid4()
        novel = _make_novel(user_id=uid)
        service._repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[reportPrivateUsage]

        result = await service.get(novel.id, uid)

        assert result == novel

    async def test_get_raises_404_when_not_found(self, service: NovelService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.get(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404


class TestNovelServiceList:
    async def test_list_returns_novels_for_user(self, service: NovelService) -> None:
        uid = uuid.uuid4()
        novels = [_make_novel(user_id=uid), _make_novel(user_id=uid)]
        service._repo.list_by_user = AsyncMock(return_value=novels)  # type: ignore[reportPrivateUsage]

        result = await service.list_novels(uid)

        assert len(result) == 2
        service._repo.list_by_user.assert_called_once_with(uid)  # type: ignore[reportPrivateUsage]


class TestNovelServiceCreate:
    async def test_create_calls_repo_and_returns_novel(self, service: NovelService) -> None:
        uid = uuid.uuid4()
        novel = _make_novel(user_id=uid)
        service._repo.create = AsyncMock(return_value=novel)  # type: ignore[reportPrivateUsage]
        request = _create_request()

        result = await service.create(uid, request)

        assert result == novel
        service._repo.create.assert_called_once_with(uid, request)  # type: ignore[reportPrivateUsage]


class TestNovelServiceUpdate:
    async def test_update_modifies_existing_novel(self, service: NovelService) -> None:
        uid = uuid.uuid4()
        novel = _make_novel(user_id=uid)
        updated = _make_novel(id=novel.id, user_id=uid, title="Updated Title")
        service._repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[reportPrivateUsage]
        service._repo.update = AsyncMock(return_value=updated)  # type: ignore[reportPrivateUsage]

        request = UpdateNovelRequest(title="Updated Title")
        result = await service.update(novel.id, uid, request)

        assert result.title == "Updated Title"

    async def test_update_raises_404_when_not_found(self, service: NovelService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.update(uuid.uuid4(), uuid.uuid4(), UpdateNovelRequest())
        assert exc.value.status_code == 404


class TestNovelServiceDelete:
    async def test_delete_calls_repo_delete(self, service: NovelService) -> None:
        uid = uuid.uuid4()
        novel = _make_novel(user_id=uid)
        service._repo.get_by_id = AsyncMock(return_value=novel)  # type: ignore[reportPrivateUsage]
        service._repo.delete = AsyncMock()  # type: ignore[reportPrivateUsage]

        await service.delete(novel.id, uid)

        service._repo.delete.assert_called_once_with(novel)  # type: ignore[reportPrivateUsage]

    async def test_delete_raises_404_when_not_found(self, service: NovelService) -> None:
        service._repo.get_by_id = AsyncMock(return_value=None)  # type: ignore[reportPrivateUsage]

        with pytest.raises(HTTPException) as exc:
            await service.delete(uuid.uuid4(), uuid.uuid4())
        assert exc.value.status_code == 404
