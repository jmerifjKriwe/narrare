"""Integration tests for the character-voice SSE endpoint (ANAL-008).

Closes the ADR-086 lazy-resolution regression contract for entry 6
(``get_character_voice_service``): invalid request bodies yield ``422``
on the real chain (the factory no longer resolves the routing cascade
pre-body-validation), and a valid body with an unconfigured provider
surfaces as a pre-header ``400`` — NOT an SSE stream (ADR-086
Decision 3).

Uses dependency override with a fake service for the happy path
(established SSE-test pattern: ``test_dialogue_coach_sse.py``,
``test_voice_check_api.py``) to drive the full router → SSE chain
deterministically (no real LLM call). The service → agent → output
chain is covered by unit tests
(``tests/unit/api/analysis/test_character_voice_service.py``).

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.analysis.schemas_character_voice import (
    CharacterVoiceResult,
    CharacterVoiceStreamEvent,
)
from narrare_core.kb.schemas.character import VoiceAnalysis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient


def _parse_sse_events(raw: str) -> list[dict[str, object]]:
    """Extract JSON data events from an SSE response body."""
    events: list[dict[str, object]] = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[len("data: ") :]))
    return events


async def _create_novel(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> str:
    """Create a novel; return the novel_id."""
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Character Voice Test Novel", "writing_language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    return novel_resp.json()["id"]


class FakeCharacterVoiceService:
    """Fake service for SSE routing tests (established pattern).

    Yields progress / result / done events directly — no LLM call, no
    TestModel (which hangs inside ASGI StreamingResponse anyio task
    groups). The service → agent → output chain is unit-tested
    separately.
    """

    async def ensure_resolved(self) -> None:
        """No-op lifecycle call — the router resolves pre-header (ADR-086)."""
        return None

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[CharacterVoiceStreamEvent]:
        del novel_id, chapter_ids, user_id  # deterministic fake

        yield CharacterVoiceStreamEvent(event="progress", progress="Profiling 1 character(s).")
        yield CharacterVoiceStreamEvent(
            event="result",
            result=CharacterVoiceResult(
                character_name="Elena",
                voice_analysis=VoiceAnalysis(formality=0.7, vocabulary_level="complex"),
                kb_entry_id=None,
            ),
        )
        yield CharacterVoiceStreamEvent(event="done", is_final=True)


class TestCharacterVoiceSSE:
    """SSE flow for POST /analysis/character-voice/{novel_id}."""

    @pytest.mark.asyncio
    async def test_sse_returns_done_after_result(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """The stream yields at least one result event + a terminal done."""
        with pytest.MonkeyPatch.context() as mp:

            async def _fake_factory(**_kwargs: object) -> FakeCharacterVoiceService:
                return FakeCharacterVoiceService()

            mp.setattr(
                "narrare.analysis.router_character_voice.get_character_voice_service",
                _fake_factory,
            )
            response = await client.post(
                f"/api/v1/analysis/character-voice/{uuid4()}",
                json={"chapter_ids": None},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse_events(response.text)
        assert len(events) >= 2  # at least progress + done
        # Last data event MUST be done (or error) — terminal:
        terminal = events[-1]
        assert terminal["event"] in ("done", "error")
        # At least one result event carries the character profile
        # (validated through the schema — proves the wire format round-trips):
        result_events = [e for e in events if e.get("event") == "result" and e.get("result")]
        assert len(result_events) == 1
        result = CharacterVoiceResult.model_validate(result_events[0]["result"])
        assert result.character_name == "Elena"

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"/api/v1/analysis/character-voice/{uuid4()}",
            json={"chapter_ids": None},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_422_when_body_invalid(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with an invalid body returns 422 (real chain).

        Regression (ADR-086, entry 6): the factory previously resolved
        the per-user routing cascade eagerly at DI-construction time.
        FastAPI solves all sub-dependencies BEFORE body validation, so
        the resolver's P2 novel guard (404 for a nonexistent novel —
        ``novel_id`` is a path param) preempted the legitimate 422 for
        the invalid body. With lazy first-use resolution the body is
        validated first.
        """
        resp = await client.post(
            f"/api/v1/analysis/character-voice/{uuid4()}",
            json={"chapter_ids": 42},  # invalid body: chapter_ids must be a list
            headers=auth_headers,
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_400_pre_header_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid body + unconfigured provider → 400 with NO SSE headers.

        ADR-086 Decision 3 (real chain): the routing cascade resolves in
        the router BEFORE the StreamingResponse is constructed, so
        ``ConfigurationError`` (fresh user, no provider) surfaces as a
        pre-header 400 — the response is JSON, never ``text/event-stream``.
        """
        novel_id = await _create_novel(client, auth_headers)

        resp = await client.post(
            f"/api/v1/analysis/character-voice/{novel_id}",
            json={"chapter_ids": None},
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert not resp.headers["content-type"].startswith("text/event-stream")
