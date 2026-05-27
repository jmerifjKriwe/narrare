"""Integration tests for writing stats and scene endpoints.

Tests ``router_stats.py`` endpoints against the real FastAPI app with
rolled-back database sessions.  LLM calls are patched via autouse fixture
in ``conftest.py`` (``FakeModelRegistry``).

Endpoint under test:
- ``GET  /writing/novels/{novel_id}/stats``
- ``POST /writing/generation/{request_id}/scene/next``
- ``POST /writing/generation/{request_id}/scene/{scene_number}/accept``

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


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
        json={"title": "Stats Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Stats Test Chapter", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


async def _start_scene_generation(
    client: AsyncClient,
    auth_headers: dict[str, str],
    novel_id: str,
    chapter_id: str,
) -> str:
    """Start a scene-by-scene generation, return request_id."""
    resp = await client.post(
        f"/api/v1/writing/chapters/{chapter_id}/generate",
        params={"novel_id": str(novel_id)},
        json={
            "mode": "scene_by_scene",
            "outline": "A hero discovers a hidden world beneath the city",
            "language": "en",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["request_id"]


# ---------------------------------------------------------------------------
# Tests — GET /writing/novels/{novel_id}/stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """Generation statistics for a novel."""

    async def test_get_stats_returns_200_for_new_novel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """A novel with zero generations returns all-zero stats."""
        novel_id, _ = await _create_novel_with_chapter(client, auth_headers)

        resp = await client.get(
            f"/api/v1/writing/novels/{novel_id}/stats",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_generations"] == 0
        assert data["success_rate"] == 0.0
        assert data["avg_tokens"] == 0.0
        assert data["avg_word_count"] == 0.0
        assert data["most_used_model"] is None

    async def test_get_stats_after_generation(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Stats reflect at least one generation after starting one."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # Start a generation
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "A tale of two cities",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert start_resp.status_code == 200
        request_id = start_resp.json()["request_id"]

        # Stop it to complete the lifecycle
        stop_resp = await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )
        assert stop_resp.status_code == 200

        # Now check stats
        stats_resp = await client.get(
            f"/api/v1/writing/novels/{novel_id}/stats",
            headers=auth_headers,
        )

        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["total_generations"] >= 1
        assert "success_rate" in stats
        assert "avg_tokens" in stats
        assert "avg_word_count" in stats
        assert "most_used_model" in stats

    async def test_get_stats_returns_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """GET stats without authentication returns 401."""
        novel_id = uuid.uuid4()

        resp = await client.get(
            f"/api/v1/writing/novels/{novel_id}/stats",
        )

        assert resp.status_code == 401

    async def test_get_stats_with_invalid_novel_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET stats with a non-UUID novel_id returns 422."""
        resp = await client.get(
            "/api/v1/writing/novels/not-a-uuid/stats",
            headers=auth_headers,
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — POST /writing/generation/{request_id}/scene/next
# ---------------------------------------------------------------------------


class TestSceneNext:
    """Request the next scene in scene-by-scene mode."""

    async def test_scene_next_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST scene/next returns SceneNextResponse with expected fields."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)
        request_id = await _start_scene_generation(
            client,
            auth_headers,
            novel_id,
            chapter_id,
        )

        resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/next",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == request_id
        assert isinstance(data["scene_number"], int)
        assert data["scene_number"] >= 1
        assert isinstance(data["status"], str)

    async def test_scene_next_returns_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """POST scene/next without authentication returns 401."""
        request_id = uuid.uuid4()

        resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/next",
        )

        assert resp.status_code == 401

    async def test_scene_next_nonexistent_request_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST scene/next for a non-existent request returns 404."""
        fake_request_id = uuid.uuid4()

        resp = await client.post(
            f"/api/v1/writing/generation/{fake_request_id}/scene/next",
            headers=auth_headers,
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — POST /writing/generation/{request_id}/scene/{scene_number}/accept
# ---------------------------------------------------------------------------


class TestAcceptScene:
    """Accept a specific scene in scene-by-scene mode."""

    async def test_accept_scene_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST scene/{n}/accept returns AcceptResponse with expected fields."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)
        request_id = await _start_scene_generation(
            client,
            auth_headers,
            novel_id,
            chapter_id,
        )

        resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/1/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == request_id
        assert "chapter_id" in data
        assert "word_count" in data

    async def test_accept_scene_returns_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """POST scene/accept without authentication returns 401."""
        request_id = uuid.uuid4()

        resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/1/accept",
        )

        assert resp.status_code == 401

    async def test_accept_scene_invalid_scene_number_returns_error(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST scene/accept with non-integer scene_number returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)
        request_id = await _start_scene_generation(
            client,
            auth_headers,
            novel_id,
            chapter_id,
        )

        # "abc" cannot be parsed as int → FastAPI returns 422
        resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/scene/abc/accept",
            headers=auth_headers,
        )

        assert resp.status_code == 422
