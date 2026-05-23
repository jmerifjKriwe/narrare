"""Integration tests for volume endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from narrare.novels.schemas import NovelResponse
from narrare.volumes.schemas import VolumeResponse

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
    validated = NovelResponse.model_validate(response.json())
    return str(validated.id)


class TestListVolumes:
    async def test_list_returns_empty_for_new_novel(
        self, client: AsyncClient, auth_headers: dict[str, str], novel_id: str
    ) -> None:
        response = await client.get(f"/api/v1/novels/{novel_id}/volumes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # New novels get an auto-created default volume
        assert len(data) == 1
        assert data[0]["is_default"] is True

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
        validated = VolumeResponse.model_validate(data)
        assert validated.title == "Book One"
        assert validated.position == 0
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
        validated = VolumeResponse.model_validate(response.json())
        assert validated.title == "Book Two"
        assert validated.position == 0


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
        validated = VolumeResponse.model_validate(response.json())
        assert validated.title == "New Title"

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


# ---------------------------------------------------------------------------
# Task 4.7: Full volume CRUD lifecycle
# ---------------------------------------------------------------------------


class TestVolumeCRUDLifecycle:
    """End-to-end lifecycle: create novel → default volume → stats → reorder → delete protection."""

    async def test_full_volume_lifecycle(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # Step 1: Create a novel — verify default volume auto-created
        novel_resp = await client.post(
            "/api/v1/novels",
            json={"title": "Lifecycle Novel"},
            headers=auth_headers,
        )
        assert novel_resp.status_code == 201
        nid = novel_resp.json()["id"]

        volumes_resp = await client.get(
            f"/api/v1/novels/{nid}/volumes",
            headers=auth_headers,
        )
        assert volumes_resp.status_code == 200
        volumes = volumes_resp.json()
        assert len(volumes) == 1
        default_volume = volumes[0]
        assert default_volume["is_default"] is True
        assert default_volume["title"] == "Volume 1"
        default_volume_id = default_volume["id"]

        # Step 2: Create additional volume → verify appears in list
        create_resp = await client.post(
            f"/api/v1/novels/{nid}/volumes",
            json={"title": "Volume 2"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        vol2 = create_resp.json()
        vol2_id = vol2["id"]
        assert vol2["position"] == 0
        assert vol2["title"] == "Volume 2"

        list_resp = await client.get(
            f"/api/v1/novels/{nid}/volumes",
            headers=auth_headers,
        )
        assert len(list_resp.json()) == 2

        # Step 3: Get volume stats → verify empty stats
        stats_resp = await client.get(
            f"/api/v1/novels/{nid}/volumes/{default_volume_id}/stats",
            headers=auth_headers,
        )
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["word_count"] == 0
        assert stats["chapter_count"] == 0

        # Step 4: Create chapter → verify assigned to default volume
        chapter_resp = await client.post(
            f"/api/v1/novels/{nid}/chapters",
            json={"title": "Chapter One", "content": "Hello world this is a test chapter"},
            headers=auth_headers,
        )
        assert chapter_resp.status_code == 201
        chapter = chapter_resp.json()
        assert chapter["volume_id"] == default_volume_id

        # Step 5: Get volume stats again → verify chapter_count=1, word_count updated
        stats_resp2 = await client.get(
            f"/api/v1/novels/{nid}/volumes/{default_volume_id}/stats",
            headers=auth_headers,
        )
        assert stats_resp2.status_code == 200
        stats2 = stats_resp2.json()
        assert stats2["chapter_count"] == 1
        assert stats2["word_count"] > 0

        # Step 6: Reorder volumes → verify new order
        reorder_resp = await client.patch(
            f"/api/v1/novels/{nid}/volumes/reorder",
            json={"volume_ids": [vol2_id, default_volume_id]},
            headers=auth_headers,
        )
        assert reorder_resp.status_code == 200
        reordered = reorder_resp.json()
        assert reordered[0]["id"] == vol2_id
        assert reordered[0]["position"] == 0
        assert reordered[1]["id"] == default_volume_id
        assert reordered[1]["position"] == 1

        # Step 7: Try delete default volume → verify 422 error
        delete_default_resp = await client.delete(
            f"/api/v1/novels/{nid}/volumes/{default_volume_id}",
            headers=auth_headers,
        )
        assert delete_default_resp.status_code == 422

        # Step 8: Delete non-default volume → verify success
        delete_resp = await client.delete(
            f"/api/v1/novels/{nid}/volumes/{vol2_id}",
            headers=auth_headers,
        )
        assert delete_resp.status_code == 204

        # Verify only the default volume remains
        final_list = await client.get(
            f"/api/v1/novels/{nid}/volumes",
            headers=auth_headers,
        )
        assert len(final_list.json()) == 1
        assert final_list.json()[0]["is_default"] is True
