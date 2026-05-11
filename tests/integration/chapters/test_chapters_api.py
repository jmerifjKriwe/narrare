"""Integration tests for chapter endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.fixture
async def novel_id(client: AsyncClient, auth_headers: dict[str, str]) -> str:
    """Create a novel and return its ID."""
    response = await client.post(
        "/api/v1/novels",
        json={"title": "Test Novel", "language": "en"},
        headers=auth_headers,
    )
    return response.json()["id"]


class TestListChapters:
    async def test_list_empty_for_new_novel(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(f"/api/v1/novels/{novel_id}/chapters", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []


class TestCreateChapter:
    async def test_create_chapter(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "Chapter One", "content": "It was a dark and stormy night."},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Chapter One"
        assert data["word_count"] == 8
        assert data["position"] == 0

    async def test_second_chapter_gets_next_position(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "Chapter One"},
            headers=auth_headers,
        )
        response = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "Chapter Two"},
            headers=auth_headers,
        )
        assert response.json()["position"] == 1


class TestUpdateChapterContent:
    async def test_autosave_updates_content(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        create = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "Chapter One", "content": "Original."},
            headers=auth_headers,
        )
        chapter_id = create.json()["id"]

        response = await client.put(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/content",
            json={"content": "Updated content with more words here."},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated content with more words here."
        assert data["word_count"] == 6

    async def test_content_too_long_returns_413(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        create = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "Big Chapter"},
            headers=auth_headers,
        )
        chapter_id = create.json()["id"]
        response = await client.put(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}/content",
            json={"content": "x" * 100_001},
            headers=auth_headers,
        )
        assert response.status_code == 413


class TestReorderChapters:
    async def test_reorder_changes_positions(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        c1 = (
            await client.post(
                f"/api/v1/novels/{novel_id}/chapters",
                json={"title": "First"},
                headers=auth_headers,
            )
        ).json()["id"]
        c2 = (
            await client.post(
                f"/api/v1/novels/{novel_id}/chapters",
                json={"title": "Second"},
                headers=auth_headers,
            )
        ).json()["id"]

        response = await client.post(
            f"/api/v1/novels/{novel_id}/chapters/reorder",
            json={"chapter_ids": [c2, c1]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        chapters = response.json()
        assert chapters[0]["id"] == c2
        assert chapters[1]["id"] == c1


class TestUpdateChapterMeta:
    async def test_update_title(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        create = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "Old Title"},
            headers=auth_headers,
        )
        chapter_id = create.json()["id"]

        response = await client.patch(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}",
            json={"title": "New Title"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"


class TestGetChapter:
    async def test_get_existing_chapter(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        create = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "Fetchable"},
            headers=auth_headers,
        )
        chapter_id = create.json()["id"]

        response = await client.get(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == chapter_id

    async def test_get_nonexistent_chapter_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        import uuid

        response = await client.get(
            f"/api/v1/novels/{novel_id}/chapters/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestDeleteChapter:
    async def test_delete_removes_chapter(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        create = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": "To Delete"},
            headers=auth_headers,
        )
        chapter_id = create.json()["id"]
        response = await client.delete(
            f"/api/v1/novels/{novel_id}/chapters/{chapter_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204
