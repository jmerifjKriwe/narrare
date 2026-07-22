"""Integration tests for the dialogue-coach SSE endpoint.

Closes the ADR-056 runtime-adoption gate for ai_assist/dialogue_coach.
Uses dependency override with a fake service (established SSE-test pattern:
``test_voice_check_api.py``, ``test_coreference_api.py``) to drive the
full router → SSE chain deterministically (no real LLM call, no
TestModel — which hangs inside ASGI StreamingResponse's anyio task group).

The service → agent → output chain is covered by unit tests
(``tests/unit/api/ai_assist/test_dialogue_coach_service.py``).

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from httpx import AsyncClient

    from narrare.ai_assist.schemas import (
        DialogueCoachRequest,
        DialogueCoachStreamEvent,
    )


def _parse_sse_events(raw: str) -> list[dict[str, object]]:
    """Extract JSON data events from an SSE response body."""
    events: list[dict[str, object]] = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[len("data: ") :]))
    return events


async def _create_chapter(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> str:
    """Create a novel + chapter; return the chapter_id."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Dialogue Coach Test Novel", "writing_language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    novel_id = novel_resp.json()["id"]

    chapter_resp = await client.post(
        f"/api/v1/novels/{novel_id}/chapters",
        json={"title": "Ch 1", "position": 1, "content": '"Hello," Alice said.'},
        headers=auth_headers,
    )
    assert chapter_resp.status_code == 201
    return chapter_resp.json()["id"]


class FakeDialogueCoachService:
    """Fake service for SSE routing tests (established pattern).

    Yields progress / result / done events directly — no LLM call, no
    TestModel (which hangs inside ASGI StreamingResponse anyio task groups).
    The service → agent → output chain is unit-tested separately.
    """

    async def stream(
        self,
        *,
        chapter_id: UUID,
        user_id: UUID,
        request: DialogueCoachRequest,
    ) -> AsyncIterator[DialogueCoachStreamEvent]:
        from narrare.ai_assist.schemas import (
            DialogueCoachResponse,
            DialogueCoachStreamEvent,
            DialogueIssueResponse,
        )

        del chapter_id, user_id, request  # deterministic fake

        yield DialogueCoachStreamEvent(event="progress", progress="Analysing dialogue…")
        yield DialogueCoachStreamEvent(
            event="result",
            result=DialogueCoachResponse(
                chapter_id="test",
                mode="analyze",
                issues=[
                    DialogueIssueResponse(
                        issue_type="voice_mismatch",
                        speaker="Alice",
                        original_quote='"Good morning."',
                        diagnosis="Too formal for Alice's terse voice.",
                        severity="medium",
                    )
                ],
                adaptive_summary="preferences + voice profiles active",
            ),
        )
        yield DialogueCoachStreamEvent(event="done", is_final=True)


class TestDialogueCoachSSE:
    """SSE flow for POST /ai-assist/dialogue-coach/{chapter_id}."""

    @pytest.mark.asyncio
    async def test_sse_returns_done_after_result(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        app: FastAPI,
    ) -> None:
        """The stream yields at least one result event + a terminal done."""
        from narrare.ai_assist.dependencies import get_dialogue_coach_service

        chapter_id = await _create_chapter(client, auth_headers)

        app.dependency_overrides[get_dialogue_coach_service] = (
            lambda: FakeDialogueCoachService()  # type: ignore[arg-type,return-value]
        )
        try:
            response = await client.post(
                f"/api/v1/ai-assist/dialogue-coach/{chapter_id}",
                json={"selection_text": '"Hello," Alice said.', "mode": "analyze"},
                headers=auth_headers,
            )
        finally:
            app.dependency_overrides.pop(get_dialogue_coach_service, None)

        assert response.status_code == 200
        events = _parse_sse_events(response.text)
        assert len(events) >= 2  # at least progress + done
        # Last data event MUST be done (or error) — terminal:
        terminal = events[-1]
        assert terminal["event"] in ("done", "error")
        # At least one result event carries the issue:
        result_events = [e for e in events if e.get("event") == "result" and e.get("result")]
        assert len(result_events) >= 1
        result = result_events[0]["result"]  # type: ignore[index]
        assert isinstance(result["issues"], list)  # type: ignore[index]
        assert len(result["issues"]) == 1  # type: ignore[index]

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"/api/v1/ai-assist/dialogue-coach/{uuid4()}",
            json={"selection_text": "x", "mode": "analyze"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_422_when_body_missing(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        chapter_id = await _create_chapter(client, auth_headers)
        response = await client.post(
            f"/api/v1/ai-assist/dialogue-coach/{chapter_id}",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_422_when_mode_invalid(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        chapter_id = await _create_chapter(client, auth_headers)
        response = await client.post(
            f"/api/v1/ai-assist/dialogue-coach/{chapter_id}",
            json={"selection_text": "x", "mode": "bad"},
            headers=auth_headers,
        )
        assert response.status_code == 422
