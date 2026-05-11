"""Integration tests for volume endpoints."""

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
        json={"title": "Volume Test Novel"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestListVolumes:
    async def test_list_returns_empty_for_new_novel(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(f"/api/v1/novels/{novel_id}/volumes", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_without_auth_returns_401(self, client: AsyncClient, novel_id: str) -> None:
        response = await client.get(f"/api/v1/novels/{novel_id}/volumes")
        assert response.status_code == 401


class TestCreateVolume:
    async def test_create_returns_volume(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.post(
            f"/api/v1/novels/{novel_id}/volumes",
            json={"title": "Book One"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Book One"
        assert data["position"] == 0
        assert "id" in data

    async def test_create_without_title_returns_422(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.post(
            f"/api/v1/novels/{novel_id}/volumes",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_second_volume_gets_next_position(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        await client.post(
            f"/api/v1/novels/{novel_id}/volumes",
            json={"title": "Book One"},
            headers=auth_headers,
        )
        response = await client.post(
            f"/api/v1/novels/{novel_id}/volumes",
            json={"title": "Book Two"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["position"] == 1


class TestUpdateVolume:
    async def test_update_title(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        create = await client.post(
            f"/api/v1/novels/{novel_id}/volumes",
            json={"title": "Old Title"},
            headers=auth_headers,
        )
        volume_id = create.json()["id"]
        response = await client.patch(
            f"/api/v1/novels/{novel_id}/volumes/{volume_id}",
            json={"title": "New Title"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    async def test_update_nonexistent_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        import uuid

        response = await client.patch(
            f"/api/v1/novels/{novel_id}/volumes/{uuid.uuid4()}",
            json={"title": "X"},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestDeleteVolume:
    async def test_delete_removes_volume(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        create = await client.post(
            f"/api/v1/novels/{novel_id}/volumes",
            json={"title": "To Delete"},
            headers=auth_headers,
        )
        volume_id = create.json()["id"]
        response = await client.delete(
            f"/api/v1/novels/{novel_id}/volumes/{volume_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

    async def test_delete_nonexistent_returns_404(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        import uuid

        response = await client.delete(
            f"/api/v1/novels/{novel_id}/volumes/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404
