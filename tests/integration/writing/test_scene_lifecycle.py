"""Integration test: scene-by-scene lifecycle — scene 1 → accept → scene 2 → accept → assembly.

Tests the scene-by-scene generation mode against the real FastAPI app with
a rolled-back database session.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.requires_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_novel_with_chapter(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> tuple[str, str]:
    """Create a novel and a chapter, return (novel_id, chapter_id)."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Scene Lifecycle Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Chapter with Scenes", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSceneBySceneLifecycle:
    """Scene-by-scene mode: start → next_scene → accept_scene → repeat."""

    async def test_scene_lifecycle_start_and_next_scene(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Start scene-by-scene generation and request first scene."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # 1. Start generation in scene-by-scene mode
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "scene_by_scene",
                "outline": "Opening: hero discovers a mysterious map",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert start_resp.status_code == 200
        data = start_resp.json()
        request_id = data["request_id"]
        assert data["mode"] == "scene_by_scene"
        assert data["status"] == "pending"

        # 2. Request next scene
        next_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/next",
            headers=auth_headers,
        )
        assert next_resp.status_code == 200
        scene_data = next_resp.json()
        assert scene_data["request_id"] == request_id
        assert "scene_number" in scene_data
        assert "status" in scene_data

    async def test_scene_lifecycle_accept_scene(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Accept a specific scene in scene-by-scene mode."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "scene_by_scene",
                "outline": "Hero enters the cave",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        # Accept scene 1
        accept_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/1/accept",
            headers=auth_headers,
        )
        assert accept_resp.status_code == 200
        accept_data = accept_resp.json()
        assert accept_data["chapter_id"] == chapter_id
        assert "word_count" in accept_data

    async def test_scene_lifecycle_multiple_scenes(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Request and accept multiple scenes sequentially."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # Start generation
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "scene_by_scene",
                "outline": "A three-act opening sequence",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        # Scene 1: request → accept
        next_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/next",
            headers=auth_headers,
        )
        assert next_resp.status_code == 200
        assert next_resp.json()["scene_number"] == 1

        accept1_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/1/accept",
            headers=auth_headers,
        )
        assert accept1_resp.status_code == 200

        # Scene 2: request → accept
        next2_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/next",
            headers=auth_headers,
        )
        assert next2_resp.status_code == 200

        accept2_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/2/accept",
            headers=auth_headers,
        )
        assert accept2_resp.status_code == 200

    async def test_scene_lifecycle_with_stop(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Scene-by-scene generation can be stopped mid-flow."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "scene_by_scene",
                "outline": "Interrupted journey",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        # Stop the generation
        stop_resp = await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "stopped"
