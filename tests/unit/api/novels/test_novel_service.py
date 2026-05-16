"""Unit tests for novels/service.py — business logic with Fake classes."""

from __future__ import annotations

import uuid

import pytest

from narrare.novels.schemas import CreateNovelRequest, UpdateNovelRequest
from narrare.novels.service import NovelService
from narrare_core.shared.errors import NotFoundError
from tests.factories import make_novel
from tests.fakes import FakeNovelRepository


@pytest.fixture
def fake_repo() -> FakeNovelRepository:
    return FakeNovelRepository()


@pytest.fixture
def service(fake_repo: FakeNovelRepository) -> NovelService:
    return NovelService(repo=fake_repo)


def _create_request(**overrides: str) -> CreateNovelRequest:
    return CreateNovelRequest(title="My Novel", **overrides)


class TestNovelServiceGet:
    async def test_get_returns_novel_when_found(
        self, service: NovelService, fake_repo: FakeNovelRepository
    ) -> None:
        uid = uuid.uuid4()
        novel = make_novel(user_id=uid)
        fake_repo.seed(novel)

        result = await service.get(novel.id, uid)
        assert result == novel

    async def test_get_raises_404_when_not_found(self, service: NovelService) -> None:
        with pytest.raises(NotFoundError):
            await service.get(uuid.uuid4(), uuid.uuid4())


class TestNovelServiceList:
    async def test_list_returns_novels_for_user(
        self, service: NovelService, fake_repo: FakeNovelRepository
    ) -> None:
        uid = uuid.uuid4()
        novels = [make_novel(user_id=uid), make_novel(user_id=uid)]
        fake_repo.seed(*novels)

        result = await service.list_novels(uid)
        assert len(result) == 2
        fake_repo.assert_called_once("list_by_user")


class TestNovelServiceCreate:
    async def test_create_calls_repo_and_returns_novel(
        self, service: NovelService, fake_repo: FakeNovelRepository
    ) -> None:
        uid = uuid.uuid4()
        request = _create_request()

        result = await service.create(uid, request)
        assert result.title == "My Novel"
        fake_repo.assert_called_once("create")


class TestNovelServiceUpdate:
    async def test_update_modifies_existing_novel(
        self, service: NovelService, fake_repo: FakeNovelRepository
    ) -> None:
        uid = uuid.uuid4()
        novel = make_novel(user_id=uid)
        fake_repo.seed(novel)

        request = UpdateNovelRequest(title="Updated Title")
        result = await service.update(novel.id, uid, request)
        assert result.title == "Updated Title"

    async def test_update_raises_404_when_not_found(self, service: NovelService) -> None:
        with pytest.raises(NotFoundError):
            await service.update(uuid.uuid4(), uuid.uuid4(), UpdateNovelRequest())


class TestNovelServiceDelete:
    async def test_delete_calls_repo_delete(
        self, service: NovelService, fake_repo: FakeNovelRepository
    ) -> None:
        uid = uuid.uuid4()
        novel = make_novel(user_id=uid)
        fake_repo.seed(novel)

        await service.delete(novel.id, uid)
        fake_repo.assert_called_once("delete")

    async def test_delete_raises_404_when_not_found(self, service: NovelService) -> None:
        with pytest.raises(NotFoundError):
            await service.delete(uuid.uuid4(), uuid.uuid4())
