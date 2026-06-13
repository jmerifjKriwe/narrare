"""Unit tests for chapter routers — CRUD and version endpoints.

Tests both narrare.chapters.router and narrare.chapters.router_versions
via httpx.AsyncClient with mocked service layer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.database import get_async_session
from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.chapters.repository import ChapterRepository
from narrare.chapters.router import _get_service as _get_chapter_service
from narrare.chapters.router_versions import _get_service as _get_version_service
from narrare.chapters.service import ChapterService
from tests.factories import make_chapter as _make_chapter_base

_NOW = datetime.now(UTC)


def _make_chapter(**overrides: Any) -> Any:
    """Create a Chapter with all required fields for response validation."""
    return _make_chapter_base(
        summary="",
        created_at=_NOW,
        updated_at=_NOW,
        **overrides,
    )


TEST_USER_ID = "00000000-0000-0000-0000-0000000000ff"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create test app with overridden dependencies."""
    application = create_app()

    async def _mock_session():
        mock = AsyncMock()
        mock.execute = AsyncMock()
        yield mock

    async def _mock_auth() -> str:
        return TEST_USER_ID

    application.dependency_overrides[get_async_session] = _mock_session
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app):
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _mock_chapter_service() -> AsyncMock:
    """Create a mock ChapterService with async methods."""
    service = AsyncMock()
    service.list_chapters = AsyncMock()
    service.get = AsyncMock()
    service.create = AsyncMock()
    service.update_content = AsyncMock()
    service.update_meta = AsyncMock()
    service.reorder = AsyncMock()
    service.delete = AsyncMock()
    service.list_versions = AsyncMock()
    service.restore_version = AsyncMock()
    return service


# ---------------------------------------------------------------------------
# list_chapters — GET /novels/{novel_id}/chapters
# ---------------------------------------------------------------------------


class TestListChapters:
    async def test_list_returns_summaries(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        chapter = _make_chapter(novel_id=novel_id, title="Ch 1", position=0)

        mock_service = _mock_chapter_service()
        mock_service.list_chapters.return_value = [chapter]
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/chapters")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Ch 1"

    async def test_list_with_volume_id_filter(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        volume_id = _uid()
        chapter = _make_chapter(novel_id=novel_id, volume_id=volume_id)

        mock_service = _mock_chapter_service()
        mock_service.list_chapters.return_value = [chapter]
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.get(
            f"/api/v1/novels/{novel_id}/chapters",
            params={"volume_id": str(volume_id)},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_service.list_chapters.assert_called_once()
        _, call_kwargs = mock_service.list_chapters.call_args
        assert call_kwargs["volume_id"] == volume_id

    async def test_list_returns_empty_when_no_chapters(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()

        mock_service = _mock_chapter_service()
        mock_service.list_chapters.return_value = []
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/chapters")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


# ---------------------------------------------------------------------------
# create_chapter — POST /novels/{novel_id}/chapters
# ---------------------------------------------------------------------------


class TestCreateChapter:
    async def test_create_returns_201_with_chapter(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        chapter = _make_chapter(novel_id=novel_id, title="New Chapter", content="text", position=1)

        mock_service = _mock_chapter_service()
        mock_service.create.return_value = chapter
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "New Chapter", "content": "text"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "New Chapter"
        assert data["content"] == "text"

    async def test_create_returns_422_for_title_too_long(
        self, app: Any, client: AsyncClient
    ) -> None:
        novel_id = _uid()

        mock_service = _mock_chapter_service()
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "x" * 501},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ---------------------------------------------------------------------------
# get_chapter — GET /novels/{novel_id}/chapters/{chapter_id}
# ---------------------------------------------------------------------------


class TestGetChapter:
    async def test_get_returns_chapter(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        chapter_id = _uid()
        chapter = _make_chapter(id=chapter_id, novel_id=novel_id, title="My Chapter")

        mock_service = _mock_chapter_service()
        mock_service.get.return_value = chapter
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "My Chapter"
        assert data["id"] == str(chapter_id)


# ---------------------------------------------------------------------------
# update_chapter_content — PUT /novels/{novel_id}/chapters/{chapter_id}/content
# ---------------------------------------------------------------------------


class TestUpdateChapterContent:
    async def test_update_content_returns_chapter(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        chapter_id = _uid()
        chapter = _make_chapter(id=chapter_id, novel_id=novel_id, content="updated")

        mock_service = _mock_chapter_service()
        mock_service.update_content.return_value = chapter
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.put(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/content",
            json={"content": "updated"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["content"] == "updated"

    async def test_update_content_returns_422_for_missing_content(
        self, app: Any, client: AsyncClient
    ) -> None:
        novel_id = _uid()
        chapter_id = _uid()

        mock_service = _mock_chapter_service()
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.put(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/content",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ---------------------------------------------------------------------------
# update_chapter_meta — PATCH /novels/{novel_id}/chapters/{chapter_id}
# ---------------------------------------------------------------------------


class TestUpdateChapterMeta:
    async def test_update_meta_returns_chapter(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        chapter_id = _uid()
        chapter = _make_chapter(id=chapter_id, novel_id=novel_id, title="Updated Title")

        mock_service = _mock_chapter_service()
        mock_service.update_meta.return_value = chapter
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.patch(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}",
            json={"title": "Updated Title"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title"] == "Updated Title"


# ---------------------------------------------------------------------------
# reorder_chapters — POST /novels/{novel_id}/chapters/reorder
# ---------------------------------------------------------------------------


class TestReorderChapters:
    async def test_reorder_returns_reordered_list(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        ch1 = _make_chapter(novel_id=novel_id, position=0)
        ch2 = _make_chapter(novel_id=novel_id, position=1)

        mock_service = _mock_chapter_service()
        mock_service.reorder.return_value = [ch1, ch2]
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/novels/{novel_id}/chapters/reorder",
            json={"chapter_ids": [str(ch1.id), str(ch2.id)]},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2


# ---------------------------------------------------------------------------
# delete_chapter — DELETE /novels/{novel_id}/chapters/{chapter_id}
# ---------------------------------------------------------------------------


class TestDeleteChapter:
    async def test_delete_returns_204(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        chapter_id = _uid()

        mock_service = _mock_chapter_service()
        mock_service.delete = AsyncMock()
        app.dependency_overrides[_get_chapter_service] = lambda: mock_service

        response = await client.delete(f"/api/v1/novels/{novel_id}/chapters/{chapter_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT


# ---------------------------------------------------------------------------
# list_chapter_versions — GET /novels/{novel_id}/chapters/{chapter_id}/versions
# ---------------------------------------------------------------------------


class TestListChapterVersions:
    async def test_list_versions_returns_version_list(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        chapter_id = _uid()

        mock_service = _mock_chapter_service()
        mock_service.list_versions.return_value = []
        app.dependency_overrides[_get_version_service] = lambda: mock_service

        response = await client.get(f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/versions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["versions"] == []
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# restore_chapter_version — POST .../versions/{version_id}/restore
# ---------------------------------------------------------------------------


class TestRestoreChapterVersion:
    async def test_restore_returns_chapter(self, app: Any, client: AsyncClient) -> None:
        novel_id = _uid()
        chapter_id = _uid()
        version_id = _uid()
        chapter = _make_chapter(id=chapter_id, novel_id=novel_id, content="restored content")

        mock_service = _mock_chapter_service()
        mock_service.restore_version.return_value = chapter
        app.dependency_overrides[_get_version_service] = lambda: mock_service

        response = await client.post(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/versions/{version_id}/restore"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["content"] == "restored content"


# ---------------------------------------------------------------------------
# _get_service DI factory — covers router_versions.py line 30
# ---------------------------------------------------------------------------


class TestGetVersionServiceFactory:
    """Test the _get_service DI factory function in router_versions.py.

    This factory is bypassed in unit tests (dependency_overrides replace it),
    so it's never executed by router tests. We test it directly here."""

    def test_get_service_constructs_chapter_service_with_real_deps(self) -> None:
        """_get_service creates a ChapterService with real repository instances.

        Covers router_versions.py:30-37 — the _get_service function body.
        """
        session = AsyncMock()
        service = _get_version_service(session)

        assert isinstance(service, ChapterService)
        assert isinstance(service._repo, ChapterRepository)
        # verify the NovelService and VolumeRepository are also real instances
        from narrare.novels.service import NovelService

        assert isinstance(service._novel_service, NovelService)
        # volume_repo should be set (not None)
        assert service._volume_repo is not None
