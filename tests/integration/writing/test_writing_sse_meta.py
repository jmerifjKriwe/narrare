"""Integration tests for context_meta SSE event in writing generation stream.

Tests verify that:
1. The first SSE event from a generation stream is a ``context_meta`` event.
2. Subsequent events contain normal text chunks.
3. The stream ends with ``[DONE]``.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create_novel_with_chapter(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> tuple[str, str]:
    """Create a novel and a chapter, return (novel_id, chapter_id)."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "SSE Meta Test Novel", "language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "SSE Meta Test Chapter", "position": 1},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    chapter_id = chapter_resp.json()["id"]

    return novel_id, chapter_id


def _parse_sse_events(raw: str) -> list[dict[str, object]]:
    """Parse SSE data lines into a list of dicts."""
    events: list[dict[str, object]] = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[len("data: ") :]))
    return events


class TestSSEContextMeta:
    """Context metadata SSE event tests."""

    @pytest.mark.asyncio
    async def test_first_sse_event_is_context_meta(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """First event in SSE stream is context_meta before text chunks."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        # Start generation
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "A test scene",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert start_resp.status_code == 200
        request_id = start_resp.json()["request_id"]

        # Read SSE stream
        stream_resp = await client.get(
            f"/api/v1/writing/generation/{request_id}/stream",
            headers=auth_headers,
        )
        assert stream_resp.status_code == 200

        events = _parse_sse_events(stream_resp.text)
        assert len(events) >= 1, "Expected at least one SSE event"

        first = events[0]
        assert first.get("type") == "context_meta"
        assert "tone" in first
        assert "kb_characters_count" in first
        assert "total_budget_tokens" in first

    @pytest.mark.asyncio
    async def test_context_meta_event_fields_match_schema(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """context_meta event contains all expected fields with correct types."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "Another test scene",
                "language": "en",
            },
            headers=auth_headers,
        )
        assert start_resp.status_code == 200
        request_id = start_resp.json()["request_id"]

        stream_resp = await client.get(
            f"/api/v1/writing/generation/{request_id}/stream",
            headers=auth_headers,
        )
        assert stream_resp.status_code == 200

        events = _parse_sse_events(stream_resp.text)
        meta_event = events[0]
        assert meta_event.get("type") == "context_meta"

        # Verify all expected fields exist
        expected_fields = [
            "type",
            "kb_characters_count",
            "kb_locations_count",
            "kb_factions_count",
            "kb_suggested_count",
            "kb_pinned_count",
            "recent_chapter_count",
            "character_names",
            "location_names",
            "faction_names",
            "is_first_chapter",
            "has_user_preferences",
            "tone",
            "total_budget_tokens",
        ]
        for field_name in expected_fields:
            assert field_name in meta_event, f"Missing field: {field_name}"

        # Verify types
        assert isinstance(meta_event["kb_characters_count"], int)
        assert isinstance(meta_event["character_names"], list)
        assert isinstance(meta_event["is_first_chapter"], bool)
        assert isinstance(meta_event["tone"], str)

    @pytest.mark.asyncio
    async def test_stream_ends_with_done(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """SSE stream terminates with [DONE] sentinel."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={
                "mode": "full_draft",
                "prompt": "Final test scene",
                "language": "en",
            },
            headers=auth_headers,
        )
        request_id = start_resp.json()["request_id"]

        stream_resp = await client.get(
            f"/api/v1/writing/generation/{request_id}/stream",
            headers=auth_headers,
        )
        assert stream_resp.status_code == 200
        assert "data: [DONE]" in stream_resp.text
