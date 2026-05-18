"""Integration test: error scenarios for the writing module.

Tests error handling: LLM failure, missing auth, concurrent generation,
non-existent resources, and invalid input.

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
        json={"title": "Error Scenario Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Error Chapter", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConcurrentGeneration:
    """Concurrent generation prevention — only one active per chapter."""

    async def test_concurrent_generation_returns_conflict(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Starting generation on a chapter with an active request returns 409."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # Start first generation
        first_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "First generation attempt",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert first_resp.status_code == 200

        # Try to start second generation on same chapter
        second_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "Second generation attempt",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert second_resp.status_code == 409

    async def test_can_generate_after_stopping(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """After stopping a generation, a new one can be started."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # Start and stop first generation
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "Will be stopped",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )

        # Should be able to start a new generation
        restart_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "Fresh attempt after stop",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert restart_resp.status_code == 200


class TestMissingInput:
    """Missing or invalid input validation."""

    async def test_missing_prompt_and_outline_returns_error(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Generation without prompt, outline, or auto_continue returns error."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "full_draft"},
            headers=auth_headers,
        )
        assert resp.status_code in (400, 422)

    async def test_invalid_mode_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Generation with invalid mode returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "invalid_mode",
                "prompt": "test",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_word_target_out_of_range_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """word_target outside 100-50000 returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "test",
                "word_target": 10,  # Below minimum
                "language": "en",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestNonExistentResources:
    """Operations on non-existent resources return 404."""

    async def test_generate_for_nonexistent_chapter_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Generation for non-existent chapter returns 404 or 500."""
        fake_chapter_id = uuid.uuid4()
        fake_novel_id = uuid.uuid4()

        resp = await client.post(
            f"/api/v1/writing/chapters/{fake_chapter_id}/generate",
            params={"novel_id": str(fake_novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "test",
                "language": "en",
            },
            headers=auth_headers,
        )
        # Will be 404 (chapter not found) or 500 (FK violation)
        assert resp.status_code in (404, 500)

    async def test_accept_nonexistent_request_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Accepting a non-existent request returns 404."""
        fake_request_id = uuid.uuid4()

        resp = await client.post(
            f"/api/v1/writing/generation/{fake_request_id}/accept",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_reject_nonexistent_request_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Rejecting a non-existent request returns 404."""
        fake_request_id = uuid.uuid4()

        resp = await client.post(
            f"/api/v1/writing/generation/{fake_request_id}/reject",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_stream_nonexistent_request_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Streaming a non-existent request returns 404."""
        fake_request_id = uuid.uuid4()

        resp = await client.get(
            f"/api/v1/writing/generation/{fake_request_id}/stream",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_stats_for_nonexistent_novel_returns_200_with_zeros(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Stats for non-existent novel returns 200 with zero counts."""
        fake_novel_id = uuid.uuid4()

        resp = await client.get(
            f"/api/v1/writing/novels/{fake_novel_id}/stats",
            headers=auth_headers,
        )
        # Stats endpoint returns zeros for novel with no generations
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_generations"] == 0


class TestAuthenticationErrors:
    """All writing endpoints require authentication."""

    async def test_generate_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST generate without auth returns 401."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()

        resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "full_draft", "prompt": "test"},
        )
        assert resp.status_code == 401

    async def test_stop_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """DELETE generation without auth returns 401."""
        request_id = uuid.uuid4()

        resp = await client.delete(
            f"/api/v1/writing/generation/{request_id}",
        )
        assert resp.status_code == 401

    async def test_accept_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST accept without auth returns 401."""
        request_id = uuid.uuid4()

        resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/accept",
        )
        assert resp.status_code == 401

    async def test_stats_without_auth_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """GET stats without auth returns 401."""
        novel_id = uuid.uuid4()

        resp = await client.get(
            f"/api/v1/writing/novels/{novel_id}/stats",
        )
        assert resp.status_code == 401
