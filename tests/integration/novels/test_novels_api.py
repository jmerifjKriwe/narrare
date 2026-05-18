"""Integration tests for novel endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.novels.schemas import NovelResponse

if TYPE_CHECKING:
    from httpx import AsyncClient

import pytest

pytestmark = pytest.mark.skip(reason="temporarily disabled due to test infrastructure issues")


class TestListNovels:
    async def test_list_returns_empty_for_new_user(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get("/api/v1/novels", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_without_auth_returns_401(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/novels")
        assert response.status_code == 401


class TestCreateNovel:
    async def test_create_returns_novel(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/novels",
            json={"title": "My Fantasy Novel", "genre": "fantasy", "language": "en"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        validated = NovelResponse.model_validate(data)
        assert validated.title == "My Fantasy Novel"
        assert validated.genre == "fantasy"
        assert "id" in data

    async def test_create_without_title_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/novels", json={"genre": "fantasy"}, headers=auth_headers
        )
        assert response.status_code == 422

    async def test_create_appears_in_list(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post("/api/v1/novels", json={"title": "Listed Novel"}, headers=auth_headers)
        response = await client.get("/api/v1/novels", headers=auth_headers)
        titles = [n["title"] for n in response.json()]
        assert "Listed Novel" in titles


class TestGetNovel:
    async def test_get_existing_novel(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create = await client.post(
            "/api/v1/novels", json={"title": "Gettable"}, headers=auth_headers
        )
        novel_id = create.json()["id"]
        response = await client.get(f"/api/v1/novels/{novel_id}", headers=auth_headers)
        assert response.status_code == 200
        validated = NovelResponse.model_validate(response.json())
        assert str(validated.id) == novel_id

    async def test_get_nonexistent_novel_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        import uuid

        response = await client.get(f"/api/v1/novels/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404


class TestUpdateNovel:
    async def test_update_title(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        create = await client.post(
            "/api/v1/novels", json={"title": "Old Title"}, headers=auth_headers
        )
        novel_id = create.json()["id"]
        response = await client.patch(
            f"/api/v1/novels/{novel_id}",
            json={"title": "New Title"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        validated = NovelResponse.model_validate(response.json())
        assert validated.title == "New Title"


class TestDeleteNovel:
    async def test_delete_removes_novel(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create = await client.post(
            "/api/v1/novels", json={"title": "To Delete"}, headers=auth_headers
        )
        novel_id = create.json()["id"]
        response = await client.delete(f"/api/v1/novels/{novel_id}", headers=auth_headers)
        assert response.status_code == 204
        get = await client.get(f"/api/v1/novels/{novel_id}", headers=auth_headers)
        assert get.status_code == 404
