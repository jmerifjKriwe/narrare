"""Integration tests for writing REST API endpoints.

Tests the full HTTP lifecycle against the real FastAPI app with
rolled-back database sessions.  LLM calls are mocked via dependency
override.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import uuid
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
        json={"title": "Test Novel for Writing", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Test Chapter", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStartGeneration:
    async def test_start_generation_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /writing/chapters/{id}/generate returns request_id."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "Write a dramatic opening scene",
                "tone": "dramatic",
                "language": "en",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "request_id" in data
        assert data["status"] == "pending"
        assert data["mode"] == "full_draft"

    async def test_start_generation_without_input_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST generate without prompt/outline/auto_continue returns error."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "full_draft"},
            headers=auth_headers,
        )

        # Should be 400 (ValidationError) or 422 from domain
        assert response.status_code in (400, 422)

    async def test_start_generation_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST generate without auth returns 401."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "full_draft", "prompt": "test"},
        )

        assert response.status_code == 401


class TestGenerationLifecycle:
    async def test_stop_generation_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """DELETE /writing/generation/{id} returns StopResponse."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        # Start a generation first
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "A scene description",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert start_resp.status_code == 200
        request_id = start_resp.json()["request_id"]

        # Stop it
        stop_resp = await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )

        assert stop_resp.status_code == 200
        data = stop_resp.json()
        assert data["status"] == "stopped"
        assert "word_count" in data

    async def test_accept_draft_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /writing/generation/{id}/accept returns AcceptResponse."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "A dramatic scene",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        # Stop first to complete it
        await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )

        # Now accept
        accept_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/accept",
            headers=auth_headers,
        )

        assert accept_resp.status_code == 200
        data = accept_resp.json()
        assert "chapter_id" in data
        assert "word_count" in data

    async def test_reject_draft_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /writing/generation/{id}/reject returns RejectResponse."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "A quiet scene",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )

        reject_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/reject",
            headers=auth_headers,
        )

        assert reject_resp.status_code == 200
        data = reject_resp.json()
        assert data["status"] == "rejected"


class TestGenerationStats:
    async def test_get_stats_returns_200(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """GET /writing/novels/{id}/stats returns GenerationStatsResponse."""
        novel_id, _ = await _create_novel_with_chapter(client, auth_headers)

        response = await client.get(
            f"/api/v1/writing/novels/{novel_id}/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_generations" in data
        assert "success_rate" in data
        assert "avg_tokens" in data
        assert "avg_word_count" in data


class TestNonExistentRequest:
    async def test_stop_nonexistent_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """DELETE /writing/generation/{id} for non-existent returns 404."""
        fake_id = uuid.uuid4()

        response = await client.delete(
            f"/api/v1/writing/generation/{fake_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404
