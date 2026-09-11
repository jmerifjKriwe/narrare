"""Integration tests for the ANAL-007 author-voice SSE API endpoint.

These tests exercise the FastAPI app's request pipeline (auth dependency,
routing, SSE serialization) with a fake service patched in. They do NOT
exercise the real analysis pipeline (that is covered by unit tests) — the
point here is the wire format + the app-level routing.

Mirrors ``test_voice_drift_api.py`` (skipped locally without Postgres; CI
runs the full integration suite).

Requires: ``just dev-services`` running (PostgreSQL on port 5433) — the
``client`` + ``app`` fixtures spin up the FastAPI app against the migrated
schema. Schema comes exclusively from Alembic migrations (RULE-14).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest

from narrare.analysis.schemas_author_voice import (
    AuthorVoiceResult,
    AuthorVoiceStreamEvent,
)
from narrare_core.profiles.author_voice import AuthorVoiceProfile
from narrare_core.schemas.voice import VoiceAnalysis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from httpx import AsyncClient


def _fake_service_factory(service: Any) -> Any:
    """Return an async factory closure for MonkeyPatch.setattr.

    The migrated dependency factories are async and accept arbitrary
    keyword arguments (session, novel_id, user_id), so the patched
    factory must be awaitable and ignore whatever the router passes
    while returning the fake service unchanged.
    """

    async def _factory(**_kwargs: object) -> Any:
        return service

    return _factory


class FakeAuthorVoiceService:
    """Fake service for app-level SSE routing tests."""

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[AuthorVoiceStreamEvent]:
        yield AuthorVoiceStreamEvent(
            event="progress", progress="Analysing author voice across 3 chapter(s)."
        )
        yield AuthorVoiceStreamEvent(
            event="result",
            result=AuthorVoiceResult(
                novel_id=str(novel_id),
                profile=AuthorVoiceProfile(
                    voice_analysis=VoiceAnalysis(
                        formality=0.7,
                        vocabulary_level="complex",
                    ),
                    author_examples=["The wind moved through the long grass."],
                ),
            ),
        )
        yield AuthorVoiceStreamEvent(event="done", is_final=True)


def _sse_payloads(text: str) -> list[str]:
    return [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: ")]


class TestAuthorVoiceAPI:
    """Author-voice streaming endpoint."""

    async def test_author_voice_streams_events_and_done_sentinel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST streams progress/result/done JSON events plus [DONE]."""
        novel_id = uuid4()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "narrare.analysis.router_author_voice.get_author_voice_service",
                _fake_service_factory(FakeAuthorVoiceService()),
            )
            resp = await client.post(
                f"/api/v1/analysis/author-voice/{novel_id}",
                headers=auth_headers,
                json={},
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        payloads = _sse_payloads(resp.text)
        progress_payload = json.loads(payloads[0])
        result_payload = json.loads(payloads[1])
        done_payload = json.loads(payloads[2])

        assert progress_payload["event"] == "progress"
        assert result_payload["event"] == "result"
        assert result_payload["result"]["novel_id"] == str(novel_id)
        assert (
            result_payload["result"]["profile"]["voice_analysis"]["vocabulary_level"] == "complex"
        )
        assert result_payload["result"]["profile"]["author_examples"] == [
            "The wind moved through the long grass."
        ]
        assert done_payload["event"] == "done"
        assert payloads[-1] == "[DONE]"

    async def test_author_voice_without_auth_returns_401(self, client: AsyncClient) -> None:
        """POST without auth headers is rejected by the app auth dependency."""
        resp = await client.post(f"/api/v1/analysis/author-voice/{uuid4()}")
        assert resp.status_code == 401

    async def test_author_voice_invalid_novel_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid UUID path parameters fail request validation."""
        resp = await client.post(
            "/api/v1/analysis/author-voice/not-a-uuid",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 422

    async def test_author_voice_route_is_registered_on_app(self, app: FastAPI) -> None:
        """The author-voice router is included under the API v1 analysis prefix."""
        registered_paths: set[str] = set()
        for route in app.routes:
            original_router = getattr(route, "original_router", None)
            include_context = getattr(route, "include_context", None)
            if original_router is None or include_context is None:
                continue
            prefix = getattr(include_context, "prefix", "")
            for child_route in original_router.routes:
                registered_paths.add(f"{prefix}{getattr(child_route, 'path', '')}")

        assert "/api/v1/analysis/author-voice/{novel_id}" in registered_paths

    async def test_author_voice_forwards_chapter_ids_in_body(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Explicit chapter_ids in the JSON body are accepted by the route."""
        novel_id = uuid4()
        # Typed container so the captured value's element type is known to
        # pyright strict mode (avoids reportUnknownArgumentType on len()).
        captured: dict[str, list[UUID] | None] = {"chapter_ids": None}

        class CapturingService:
            async def analyze(
                self,
                novel_id: UUID,
                chapter_ids: list[UUID] | None,
                user_id: UUID,
            ) -> AsyncIterator[AuthorVoiceStreamEvent]:
                captured["chapter_ids"] = chapter_ids
                yield AuthorVoiceStreamEvent(event="done", is_final=True)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "narrare.analysis.router_author_voice.get_author_voice_service",
                _fake_service_factory(CapturingService()),
            )
            resp = await client.post(
                f"/api/v1/analysis/author-voice/{novel_id}",
                headers=auth_headers,
                json={"chapter_ids": [str(uuid4()), str(uuid4())]},
            )

        assert resp.status_code == 200
        captured_ids = captured["chapter_ids"]
        assert captured_ids is not None
        assert len(captured_ids) == 2
