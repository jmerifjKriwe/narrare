"""Integration test: full generation lifecycle — start → stream → accept → chapter updated.

Tests the complete draft generation flow against the real FastAPI app with
a rolled-back database session.  LLM calls are mocked via the fake gateway.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

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
        json={"title": "Lifecycle Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Chapter 1", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullDraftLifecycle:
    """Start generation → stream text → stop → accept → verify chapter updated."""

    async def test_full_lifecycle_start_stream_accept(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Full lifecycle: start → stop → accept → chapter has content."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # 1. Start generation
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "A hero enters the dark forest",
                "word_target": 500,
                "language": "en",
            },
            headers=auth_headers,
        )
        assert start_resp.status_code == 200
        data = start_resp.json()
        request_id = data["request_id"]
        assert data["status"] == "pending"
        assert data["mode"] == "full_draft"

        # 2. Stop generation (completes it in current implementation)
        stop_resp = await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )
        assert stop_resp.status_code == 200
        stop_data = stop_resp.json()
        assert stop_data["status"] == "stopped"
        assert "word_count" in stop_data

        # 3. Accept draft — the FE always sends the accepted text as
        # ``modified_text`` (Task 3 body contract), which is what passes the
        # M06 EMPTY_DRAFT guard here: the test double's background stream has
        # not accumulated row text by stop time (word_count stays 0), and a
        # body-less accept of that row is exactly the hole the guard closes.
        accept_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/accept",
            json={"modified_text": "The hero stepped into the dark forest."},
            headers=auth_headers,
        )
        assert accept_resp.status_code == 200
        accept_data = accept_resp.json()
        assert accept_data["chapter_id"] == chapter_id
        assert "word_count" in accept_data

    async def test_full_lifecycle_start_reject(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Full lifecycle: start → stop → reject → request marked rejected."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "A quiet village scene",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert start_resp.status_code == 200
        request_id = start_resp.json()["request_id"]

        # Stop to complete
        await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )

        # Reject
        reject_resp = await client.post(
            f"/api/v1/writing/generation/{request_id}/reject",
            headers=auth_headers,
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "rejected"

    async def test_lifecycle_stream_endpoint_returns_event_stream(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """SSE stream endpoint returns text/event-stream content type."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "The wind howled through the canyon",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        # Request stream
        stream_resp = await client.get(
            f"/api/v1/writing/generation/{request_id}/stream",
            headers=auth_headers,
        )
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")

    async def test_lifecycle_stats_after_generation(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Stats endpoint reflects completed generation."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # Start and stop a generation
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "A tale of adventure",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        await client.delete(
            f"/api/v1/writing/generation/{request_id}",
            headers=auth_headers,
        )

        # Check stats
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
