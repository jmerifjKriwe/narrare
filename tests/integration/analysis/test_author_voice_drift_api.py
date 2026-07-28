"""Integration tests for the ANAL-009 Phase 2B author-voice-drift SSE API endpoint.

These tests exercise the FastAPI app's request pipeline (auth dependency,
routing, SSE serialization) with a fake service patched in. They do NOT
exercise the real analysis pipeline (that is covered by unit tests) — the
point here is the wire format + the app-level routing.

Mirrors ``test_author_voice_api.py`` (Phase 2A) + ``test_voice_drift_api.py``
(Phase 1). Auto-skipped locally without Postgres (conftest skips when the DB
is unavailable); CI runs the full integration suite.

Requires: ``just dev-services`` running (PostgreSQL on port 5433) — the
``client`` + ``app`` fixtures spin up the FastAPI app against the migrated
schema. Schema comes exclusively from Alembic migrations (RULE-14).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest

from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftEvent,
    AuthorVoiceDriftNoProfile,
    AuthorVoiceDriftRequest,
    AuthorVoiceDriftResult,
)
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from httpx import AsyncClient


def _fake_service_factory(service: Any) -> Any:
    """Return a factory closure with a typed parameter for MonkeyPatch.setattr.

    Pyright's strict mode flags ``lambda _session: Service()`` because the
    lambda parameter type is unknown. A named closure with an explicit
    ``Any`` annotation satisfies the checker while preserving the runtime
    behaviour (the dependency-injection factory ignores its session argument).
    """

    def _factory(_session: Any) -> Any:
        return service

    return _factory


class FakeAuthorVoiceDriftService:
    """Fake service for app-level SSE routing tests."""

    async def run_stream(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AsyncIterator[AuthorVoiceDriftEvent]:
        """Yield a progress, a narrator result, and a terminal done event."""
        yield AuthorVoiceDriftEvent(
            event="progress",
            progress="Analysing author-voice drift across 3 chapter(s).",
        )
        yield AuthorVoiceDriftEvent(
            event="result",
            result=AuthorVoiceDriftResult(
                novel_id=str(novel_id),
                overall_match_score=80.0,
                overall_band="minor",
                drift=VoiceDriftResult(drift_type="evolution", confidence=0.6),
            ),
        )
        yield AuthorVoiceDriftEvent(event="done", is_final=True)


def _sse_payloads(text: str) -> list[str]:
    return [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: ")]


class TestAuthorVoiceDriftAPI:
    """Author-voice-drift streaming endpoint."""

    async def test_streams_events_and_done_sentinel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST streams progress/result/done JSON events plus [DONE]."""
        novel_id = uuid4()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "narrare.analysis.router_author_voice_drift.get_author_voice_drift_service",
                _fake_service_factory(FakeAuthorVoiceDriftService()),
            )
            resp = await client.post(
                f"/api/v1/analysis/author-voice-drift/{novel_id}",
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
        assert result_payload["result"]["overall_band"] == "minor"
        assert result_payload["result"]["drift"]["drift_type"] == "evolution"
        assert done_payload["event"] == "done"
        assert payloads[-1] == "[DONE]"

    async def test_streams_no_profile_event(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """The RULE-11 graceful no_profile skip flows through the SSE route."""

        class NoProfileService:
            async def run_stream(
                self,
                novel_id: UUID,
                user_id: UUID,
                request: AuthorVoiceDriftRequest,
            ) -> AsyncIterator[AuthorVoiceDriftEvent]:
                yield AuthorVoiceDriftEvent(
                    event="no_profile",
                    no_profile=AuthorVoiceDriftNoProfile(reason="no_stored_profile"),
                )
                yield AuthorVoiceDriftEvent(event="done", is_final=True)

        novel_id = uuid4()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "narrare.analysis.router_author_voice_drift.get_author_voice_drift_service",
                _fake_service_factory(NoProfileService()),
            )
            resp = await client.post(
                f"/api/v1/analysis/author-voice-drift/{novel_id}",
                headers=auth_headers,
                json={},
            )

        assert resp.status_code == 200
        payloads = _sse_payloads(resp.text)
        no_profile_payload = json.loads(payloads[0])
        done_payload = json.loads(payloads[1])

        assert no_profile_payload["event"] == "no_profile"
        assert no_profile_payload["no_profile"]["reason"] == "no_stored_profile"
        assert done_payload["event"] == "done"
        assert payloads[-1] == "[DONE]"

    async def test_without_auth_returns_401(self, client: AsyncClient) -> None:
        """POST without auth headers is rejected by the app auth dependency."""
        resp = await client.post(f"/api/v1/analysis/author-voice-drift/{uuid4()}")
        assert resp.status_code == 401

    async def test_invalid_novel_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid UUID path parameters fail request validation."""
        resp = await client.post(
            "/api/v1/analysis/author-voice-drift/not-a-uuid",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 422

    async def test_route_is_registered_on_app(self, app: FastAPI) -> None:
        """The author-voice-drift router is included under the API v1 analysis prefix."""
        registered_paths: set[str] = set()
        for route in app.routes:
            original_router = getattr(route, "original_router", None)
            include_context = getattr(route, "include_context", None)
            if original_router is None or include_context is None:
                continue
            prefix = getattr(include_context, "prefix", "")
            for child_route in original_router.routes:
                registered_paths.add(f"{prefix}{getattr(child_route, 'path', '')}")

        assert "/api/v1/analysis/author-voice-drift/{novel_id}" in registered_paths

    async def test_forwards_chapter_ids_in_body(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Explicit chapter_ids in the JSON body are accepted by the route."""
        novel_id = uuid4()
        captured: dict[str, AuthorVoiceDriftRequest | None] = {"request": None}

        class CapturingService:
            async def run_stream(
                self,
                novel_id: UUID,
                user_id: UUID,
                request: AuthorVoiceDriftRequest,
            ) -> AsyncIterator[AuthorVoiceDriftEvent]:
                captured["request"] = request
                yield AuthorVoiceDriftEvent(event="done", is_final=True)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "narrare.analysis.router_author_voice_drift.get_author_voice_drift_service",
                _fake_service_factory(CapturingService()),
            )
            resp = await client.post(
                f"/api/v1/analysis/author-voice-drift/{novel_id}",
                headers=auth_headers,
                json={"chapter_ids": [str(uuid4()), str(uuid4())]},
            )

        assert resp.status_code == 200
        request = captured["request"]
        assert request is not None
        assert request.chapter_ids is not None
        assert len(request.chapter_ids) == 2
