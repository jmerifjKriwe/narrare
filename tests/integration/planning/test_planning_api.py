"""Integration tests for planning API endpoints.

Full API test cycle: create novel + chapters → GET storyboard → verify
auto-created outlines → PUT outline → POST remap → verify changes.
Also tests error cases (404 for non-existent novel/chapter).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.requires_db


@pytest.fixture
async def novel_with_chapters(
    client: AsyncClient, auth_headers: dict[str, str]
) -> dict[str, object]:
    """Create a novel with 3 chapters and return IDs."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_ids = []
    for i in range(3):
        ch_resp = await client.post(
            f"/api/v1/novels/{novel_id}/chapters",
            json={"title": f"Chapter {i + 1}", "content": f"Content for chapter {i + 1}."},
            headers=auth_headers,
        )
        assert ch_resp.status_code == 201
        chapter_ids.append(ch_resp.json()["id"])

    return {"novel_id": novel_id, "chapter_ids": chapter_ids}


class TestGetStoryboard:
    async def test_get_storyboard_auto_creates_outlines(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        resp = await client.get(
            f"/api/v1/planning/storyboard/{novel_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["structure_type"] == "three_act"
        assert len(data["stages"]) == 3

        total_chapters = sum(len(s["chapters"]) for s in data["stages"])
        assert total_chapters == 3

    async def test_get_storyboard_nonexistent_novel_returns_error(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        import uuid

        resp = await client.get(
            f"/api/v1/planning/storyboard/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404  # NotFoundError


class TestGetSyncStatus:
    async def test_get_sync_status(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        resp = await client.get(
            f"/api/v1/planning/storyboard/{novel_id}/sync",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        for item in data:
            assert "chapter_id" in item
            assert "sync_status" in item


class TestOutlineCRUD:
    async def test_get_or_create_outline(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]
        chapter_ids = cast("list[str]", novel_with_chapters["chapter_ids"])
        chapter_id = chapter_ids[0]

        resp = await client.get(
            f"/api/v1/planning/outlines/{novel_id}/{chapter_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_id"] == chapter_id
        assert data["stage_assignment"]  # auto-assigned

    async def test_update_outline(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]
        chapter_ids = cast("list[str]", novel_with_chapters["chapter_ids"])
        chapter_id = chapter_ids[0]

        resp = await client.put(
            f"/api/v1/planning/outlines/{novel_id}/{chapter_id}",
            json={
                "stage_assignment": "act-2",
                "outline_notes": "Updated notes",
                "planned_beats": [
                    {"title": "Beat 1", "description": "First beat", "completed": False}
                ],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage_assignment"] == "act-2"
        assert data["outline_notes"] == "Updated notes"
        assert len(data["planned_beats"]) == 1

    async def test_get_outline_nonexistent_chapter_returns_error(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        import uuid

        novel_id = novel_with_chapters["novel_id"]

        resp = await client.get(
            f"/api/v1/planning/outlines/{novel_id}/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404  # NotFoundError


class TestRemap:
    async def test_preview_remap(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        # First, get the storyboard to auto-create outlines
        await client.get(
            f"/api/v1/planning/storyboard/{novel_id}",
            headers=auth_headers,
        )

        # Preview remap to five_act
        resp = await client.post(
            f"/api/v1/planning/storyboard/{novel_id}/remap",
            json={"new_structure": "five_act", "confirm": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["new_structure"] == "five_act"
        assert data["confirmed"] is False
        assert len(data["remapped"]) == 3

    async def test_confirm_remap(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        novel_with_chapters: dict[str, object],
    ) -> None:
        novel_id = novel_with_chapters["novel_id"]

        # First, get the storyboard to auto-create outlines
        await client.get(
            f"/api/v1/planning/storyboard/{novel_id}",
            headers=auth_headers,
        )

        # Confirm remap to five_act
        resp = await client.post(
            f"/api/v1/planning/storyboard/{novel_id}/remap",
            json={"new_structure": "five_act", "confirm": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["new_structure"] == "five_act"
        assert data["confirmed"] is True
        assert len(data["remapped"]) == 3

        # Verify the storyboard now uses five_act
        sb_resp = await client.get(
            f"/api/v1/planning/storyboard/{novel_id}",
            headers=auth_headers,
        )
        assert sb_resp.status_code == 200
        assert sb_resp.json()["structure_type"] == "five_act"
