"""Integration tests for the coreference SSE endpoint (ANAL-005).

Closes the ADR-086 lazy-resolution regression contract for entry 7
(``get_coreference_service``): invalid request input yields ``422`` on
the real chain (the factory no longer resolves the routing cascade
pre-body-validation), and a valid request with an unconfigured provider
surfaces as a pre-header ``400`` — NOT an SSE stream (ADR-086
Decision 3).

Uses a fake service patched onto the router module for the happy path
(established SSE-test pattern: ``test_character_voice_api.py``,
``test_voice_check_api.py``) to drive the full router → SSE chain
deterministically (no real LLM call). The service → agent → output
chain is covered by unit tests
(``tests/unit/api/analysis/test_coreference_service.py``).

Requires: ``just dev-services`` running (PostgreSQL on port 5433).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.analysis.schemas_coreference import (
    CoreferenceResponse,
    CoreferenceStreamEvent,
)

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


class FakeCoreferenceService:
    """Fake service for SSE routing tests (established pattern).

    Yields result / done events directly — no LLM call, no TestModel
    (which hangs inside ASGI StreamingResponse anyio task groups). The
    service → agent → output chain is unit-tested separately.
    """

    async def ensure_resolved(self) -> None:
        """No-op lifecycle call — the router resolves pre-header (ADR-086)."""
        return None

    async def analyze(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[CoreferenceStreamEvent]:
        del chapter_id, user_id  # deterministic fake

        yield CoreferenceStreamEvent(
            event="result",
            result=CoreferenceResponse(
                chapter_id=str(uuid4()),
                clarity_score=82.0,
                summary="Most pronouns resolve clearly.",
                resolutions=[],
                character_mentions=[],
            ),
        )
        yield CoreferenceStreamEvent(event="done", is_final=True)


class TestCoreferenceSSE:
    """SSE flow for POST /analysis/coreference/{chapter_id}."""

    @pytest.mark.asyncio
    async def test_sse_returns_done_after_result(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """The stream yields one result event + a terminal done."""
        with pytest.MonkeyPatch.context() as mp:

            async def _fake_factory(**_kwargs: object) -> FakeCoreferenceService:
                return FakeCoreferenceService()

            mp.setattr(
                "narrare.analysis.router_coreference.get_coreference_service",
                _fake_factory,
            )
            response = await client.post(
                f"/api/v1/analysis/coreference/{uuid4()}",
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = _parse_sse_events(response.text)
        assert len(events) == 2  # result + done
        # Last data event MUST be done (or error) — terminal:
        terminal = events[-1]
        assert terminal["event"] in ("done", "error")
        # The result event carries the analysis (validated through the
        # schema — proves the wire format round-trips):
        result_events = [e for e in events if e.get("event") == "result" and e.get("result")]
        assert len(result_events) == 1
        result = CoreferenceResponse.model_validate(result_events[0]["result"])
        assert result.clarity_score == 82.0

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            f"/api/v1/analysis/coreference/{uuid4()}",
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_422_when_chapter_id_invalid(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST with an invalid chapter_id path param returns 422 (real chain).

        Regression (ADR-086, entry 7): the factory previously resolved
        the per-user routing cascade eagerly at DI-construction time.
        FastAPI solves all sub-dependencies BEFORE request validation,
        so with an unconfigured provider the eager resolve preempted the
        legitimate 422 for the malformed path param with a 400. With
        lazy first-use resolution the path param is validated first.
        """
        resp = await client.post(
            "/api/v1/analysis/coreference/not-a-uuid",
            headers=auth_headers,
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_400_pre_header_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid chapter_id + unconfigured provider → 400 with NO SSE headers.

        ADR-086 Decision 3 (real chain): the routing cascade resolves in
        the router BEFORE the StreamingResponse is constructed, so
        ``ConfigurationError`` (fresh user, no provider) surfaces as a
        pre-header 400 — the response is JSON, never ``text/event-stream``.
        The cascade resolves without the project tier (chapter-scoped
        route), so no novel needs to exist.
        """
        resp = await client.post(
            f"/api/v1/analysis/coreference/{uuid4()}",
            headers=auth_headers,
        )

        assert resp.status_code == 400
        assert not resp.headers["content-type"].startswith("text/event-stream")
