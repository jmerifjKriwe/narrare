"""Integration tests for writing rewrite validation and concurrency.

Split from test_rewrite_api.py per RULE-04 (file size limit).

Tests:
- Validation errors (selection length, mode requirements, auth)
- Concurrency and access control

LLM calls are mocked via dependency override in conftest.py.

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


# Minimal valid selection text (>=50 chars)
_SELECTION_TEXT = (
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
        json={"title": "Test Novel for Rewrite Validation", "language": "en"},
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
# Tests: Validation errors
# ---------------------------------------------------------------------------


class TestRewriteValidation:
    async def test_selection_too_short_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with selection_text < 50 chars returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": "Too short text",
                "mode": "tone",
            },
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_selection_too_long_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with selection_text > 2000 chars returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": "x" * 2001,
                "mode": "tone",
            },
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_voice_mode_without_character_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with voice mode but no character_id returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "voice",
            },
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_custom_mode_without_instructions_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite with custom mode but no custom_instructions returns 422."""
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "custom",
            },
            headers=auth_headers,
        )

        assert response.status_code == 422

    async def test_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /rewrite without auth returns 401."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
            },
        )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: Concurrency + access control
# ---------------------------------------------------------------------------


class TestRewriteConcurrency:
    async def test_concurrent_rewrite_returns_409(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite while another generation is active returns 409.

        Uses the standard /generate endpoint to create an active "pending"
        request, then verifies /rewrite detects the conflict.
        """
        novel_id, chapter_id = await _create_novel_with_chapter(
            client,
            auth_headers,
        )

        # Create an active generation request (pending — won't auto-complete)
        start_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/generate",
            params={"novel_id": str(novel_id)},
            json={"mode": "full_draft", "prompt": "A test scene"},
            headers=auth_headers,
        )
        assert start_resp.status_code == 200

        # Now try rewrite — should get 409 because there's an active generation
        rewrite_resp = await client.post(
            f"/api/v1/writing/chapters/{chapter_id}/rewrite",
            params={"novel_id": str(novel_id)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
            },
            headers=auth_headers,
        )
        assert rewrite_resp.status_code == 409

    async def test_rewrite_nonexistent_chapter_returns_404(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST /rewrite for nonexistent chapter returns 404."""
        fake_chapter = uuid.uuid4()
        fake_novel = uuid.uuid4()

        response = await client.post(
            f"/api/v1/writing/chapters/{fake_chapter}/rewrite",
            params={"novel_id": str(fake_novel)},
            json={
                "selection_text": _SELECTION_TEXT,
                "mode": "tone",
            },
            headers=auth_headers,
        )

        assert response.status_code == 404
