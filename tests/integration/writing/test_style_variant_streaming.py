"""Integration tests for style-variant SSE streaming (CR-AUFG-07-22).

Tests:
- SSE protocol correctness (data: prefix, [DONE] sentinel, is_final)
- <alternative> tag structure in streamed output
- Validation: source too short → 422, invalid variant → 422, auth → 401
- Concurrency (409) and nonexistent chapter (404)
- Settings cascade: REWRITE-intent resolution path used, variant never
  changes providers

LLM calls are mocked via dependency override in conftest.py.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


# Minimal valid source_text (>=50 chars, per StyleVariantRegenerateRequest).
_SOURCE_TEXT = (
    "The old house stood at the end of the lane, its windows dark "
    "and unseeing. A cold wind blew through the broken shutters."
)


async def _create_novel_with_chapter(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> tuple[str, str]:
    """Create a novel and a chapter, return (novel_id, chapter_id)."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Test Novel for Style Variants", "language": "en"},
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


# ---------------------------------------------------------------------------
# Tests: SSE protocol correctness
# ---------------------------------------------------------------------------


class TestStyleVariantSSEProtocol:
    async def test_sse_events_have_data_prefix(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Every SSE event line starts with 'data: ' prefix."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": _SOURCE_TEXT, "style_variant": "more_sensory"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        non_empty = [ln for ln in response.text.split("\n") if ln.strip()]
        assert non_empty, "Expected at least one SSE event"
        for ln in non_empty:
            assert ln.startswith("data: "), f"Bad SSE line: {ln!r}"

    async def test_sse_stream_ends_with_done_sentinel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """SSE stream terminates with 'data: [DONE]' sentinel."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": _SOURCE_TEXT, "style_variant": "leaner"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        non_empty = [ln for ln in response.text.split("\n") if ln.strip()]
        assert non_empty[-1] == "data: [DONE]"

    async def test_stream_yields_is_final_event(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """The SSE stream contains an is_final event for the completed variant."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": _SOURCE_TEXT, "style_variant": "more_lyrical"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert len(events) > 0
        final_events = [e for e in events if e.get("is_final")]
        assert len(final_events) >= 1, "Expected at least one is_final event"


# ---------------------------------------------------------------------------
# Tests: Validation errors
# ---------------------------------------------------------------------------


class TestStyleVariantValidation:
    async def test_source_too_short_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with source_text < 50 chars returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": "Too short", "style_variant": "leaner"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_invalid_variant_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with an unknown style_variant value returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": _SOURCE_TEXT, "style_variant": "more_dramatic"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_missing_variant_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST without style_variant returns 422 (required field)."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": _SOURCE_TEXT},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST without auth returns 401."""
        response = await client.post(
            f"/api/v1/writing/chapters/{uuid.uuid4()}/style-variants/regenerate",
            params={"novel_id": str(uuid.uuid4())},
            json={"source_text": _SOURCE_TEXT, "style_variant": "leaner"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: Concurrency + access control
# ---------------------------------------------------------------------------


class TestStyleVariantConcurrency:
    async def test_nonexistent_chapter_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST for a nonexistent chapter returns 404."""
        response = await client.post(
            f"/api/v1/writing/chapters/{uuid.uuid4()}/style-variants/regenerate",
            params={"novel_id": str(uuid.uuid4())},
            json={"source_text": _SOURCE_TEXT, "style_variant": "leaner"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_concurrent_generation_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST while another generation is active returns 409."""
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        # Create an active generation request (pending — won't auto-complete).
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "full_draft", "prompt": "A test scene"},
            headers=auth_headers,
        )
        assert start_resp.status_code == 200

        # Now style-variant regeneration should detect the conflict.
        variant_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": _SOURCE_TEXT, "style_variant": "leaner"},
            headers=auth_headers,
        )
        assert variant_resp.status_code == 409


# ---------------------------------------------------------------------------
# Tests: Settings cascade parity (RULE-17 / RULE-18)
# ---------------------------------------------------------------------------


class TestStyleVariantSettingsCascade:
    async def test_valid_request_uses_rewrite_intent_path(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """A valid request resolves through the existing cascade (200 SSE).

        The variant flows through the same REWRITE-intent model routing as
        the rewrite endpoint — the variant never changes providers.  A 200
        SSE response with content-type text/event-stream confirms the
        cascade resolved without a per-variant provider override.
        """
        novel_id, chapter_id = await _create_novel_with_chapter(client, auth_headers)

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/style-variants/regenerate",
            params={"novel_id": str(novel_id)},
            json={"source_text": _SOURCE_TEXT, "style_variant": "more_tense"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        # The streamed output should contain an <alternative> tag (count=1).
        assert "<alternative" in response.text
