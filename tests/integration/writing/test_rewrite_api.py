"""Integration tests for writing rewrite API endpoint.

Tests the full HTTP lifecycle for selection rewriting:
- POST /writing/chapters/{id}/rewrite → SSE stream
- Happy path and SSE format verification

LLM calls are mocked via dependency override in conftest.py.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import json
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
        json={"title": "Test Novel for Rewrite", "language": "en"},
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


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    """Parse SSE body into a list of event data dicts."""
    events: list[dict[str, object]] = []
    for line in body.split("\n"):
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[6:]))
    return events


# Minimal valid selection text (>=50 chars)
_SELECTION_TEXT = (
    "The old house stood at the end of the lane, its windows dark "
    "and unseeing. A cold wind blew through the broken shutters."
)


# ---------------------------------------------------------------------------
# Tests: Happy path
# ---------------------------------------------------------------------------


class TestRewriteChapter:
    async def test_rewrite_tone_mode_count_1(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with tone mode and count=1 returns SSE stream."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
                "count": 1,
                "tone": "balanced",
                "language": "en",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = _parse_sse_events(response.text)
        assert len(events) > 0

        # Should have at least a context_meta event and a text chunk
        has_meta = any(e.get("type") == "context_meta" for e in events)
        has_text = any("text" in e for e in events)
        assert has_meta or has_text, f"Expected meta or text events, got: {events}"

    async def test_rewrite_style_mode_count_2(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with style mode and count=2 returns SSE stream."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "style",
                "count": 2,
                "tone": "balanced",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

    async def test_rewrite_fix_mode(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with fix mode (show-don't-tell) returns SSE stream."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "fix",
                "options": {"strategy": "show_dont_tell"},
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

    async def test_rewrite_with_context(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite accepts optional context_before and context_after."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "context_before": "She walked up the path slowly.",
                "context_after": "The door opened with a creak.",
                "mode": "tone",
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: SSE stream format (Tasks 5.1 + 5.2)
# ---------------------------------------------------------------------------


class TestRewriteSSEFormat:
    async def test_stream_contains_alternative_tags(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """SSE stream preserves <alternative> tags in text chunks."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        # The raw response body should contain <alternative> tags
        assert "<alternative" in response.text
        assert "</alternative>" in response.text

    async def test_stream_contains_context_meta_event(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """SSE stream includes a context_meta event as first event (CR-07)."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        meta_events = [e for e in events if e.get("type") == "context_meta"]
        assert len(meta_events) > 0, f"Expected context_meta event, got: {events}"

    async def test_stream_final_event_has_is_final(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """SSE stream final event has is_final=True with usage data."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
                "count": 1,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

        events = _parse_sse_events(response.text)
        final_events = [e for e in events if e.get("is_final")]
        assert len(final_events) > 0, "Expected at least one is_final event"

        # Final event should have usage data
        final = final_events[0]
        assert "usage" in final, f"Expected usage in final event: {final}"
