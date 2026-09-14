"""Integration tests for the ANAL-009 voice-drift SSE API endpoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.analysis.schemas_voice_drift import (
    VoiceDriftCharacterResult,
    VoiceDriftEvent,
    VoiceDriftNoProfile,
    VoiceDriftRequest,
)
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from httpx import AsyncClient


class FakeVoiceDriftService:
    """Fake service for app-level SSE routing tests."""

    async def ensure_resolved(self) -> None:
        """No-op lifecycle call — the router resolves pre-header (ADR-086)."""
        return None

    async def run_stream(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: VoiceDriftRequest,
    ) -> AsyncIterator[VoiceDriftEvent]:
        """Yield one character_result, one no_profile, and a terminal done event."""
        yield VoiceDriftEvent(event="progress", progress="Analysing voice drift.")
        yield VoiceDriftEvent(
            event="character_result",
            result=VoiceDriftCharacterResult(
                character_id="char-1",
                character_name="Elena",
                overall_match_score=90.0,
                overall_band="stable",
                drift=VoiceDriftResult(drift_type="evolution", confidence=0.6),
            ),
        )
        yield VoiceDriftEvent(
            event="no_profile",
            no_profile=VoiceDriftNoProfile(
                character_name="Marc",
                reason="no_stored_profile",
            ),
        )
        yield VoiceDriftEvent(event="done", is_final=True)


def _sse_payloads(text: str) -> list[str]:
    return [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: ")]


async def _create_novel(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> str:
    """Create a novel; return the novel_id.

    Needed for the 400-pre-header node: the routing resolver's internal
    P2 novel-existence guard runs inside the cascade and would preempt
    the ``ConfigurationError`` with a 404 for a nonexistent novel.
    """
    novel_resp = await client.post(
        "/api/v1/novels",
        json={"title": "Voice Drift Test Novel", "writing_language": "en"},
        headers=auth_headers,
    )
    assert novel_resp.status_code == 201
    return novel_resp.json()["id"]


class TestVoiceDriftAPI:
    """Voice-drift streaming endpoint."""

    async def test_voice_drift_streams_events_and_done_sentinel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST streams progress/character_result/no_profile/done JSON events plus [DONE]."""
        with pytest.MonkeyPatch.context() as mp:

            async def _fake_factory(**_kwargs: object) -> FakeVoiceDriftService:
                return FakeVoiceDriftService()

            mp.setattr(
                "narrare.analysis.router_voice_drift.get_voice_drift_service",
                _fake_factory,
            )
            resp = await client.post(
                f"/api/v1/analysis/voice-drift/{uuid4()}",
                headers=auth_headers,
                json={},
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        payloads = _sse_payloads(resp.text)
        progress_payload = json.loads(payloads[0])
        result_payload = json.loads(payloads[1])
        no_profile_payload = json.loads(payloads[2])
        done_payload = json.loads(payloads[3])

        assert progress_payload["event"] == "progress"
        assert result_payload["event"] == "character_result"
        assert result_payload["result"]["character_name"] == "Elena"
        assert result_payload["result"]["drift"]["drift_type"] == "evolution"
        assert no_profile_payload["event"] == "no_profile"
        assert no_profile_payload["no_profile"]["character_name"] == "Marc"
        assert done_payload["event"] == "done"
        assert payloads[-1] == "[DONE]"

    async def test_voice_drift_without_auth_returns_401(self, client: AsyncClient) -> None:
        """POST without auth headers is rejected by the app auth dependency."""
        resp = await client.post(f"/api/v1/analysis/voice-drift/{uuid4()}")

        assert resp.status_code == 401

    async def test_voice_drift_invalid_novel_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid UUID path parameters fail request validation."""
        resp = await client.post(
            "/api/v1/analysis/voice-drift/not-a-uuid",
            headers=auth_headers,
            json={},
        )

        assert resp.status_code == 422

    async def test_voice_drift_route_is_registered_on_app(self, app: FastAPI) -> None:
        """The voice-drift router is included under the API v1 analysis prefix."""
        registered_paths: set[str] = set()
        for route in app.routes:
            original_router = getattr(route, "original_router", None)
            include_context = getattr(route, "include_context", None)
            if original_router is None or include_context is None:
                continue
            prefix = getattr(include_context, "prefix", "")
            for child_route in original_router.routes:
                registered_paths.add(f"{prefix}{getattr(child_route, 'path', '')}")

        assert "/api/v1/analysis/voice-drift/{novel_id}" in registered_paths

    async def test_voice_drift_400_pre_header_when_provider_unconfigured(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Valid body + unconfigured provider → 400 with NO SSE headers.

        ADR-086 Decision 3 (real chain): the routing cascade resolves in
        the router BEFORE the StreamingResponse is constructed, so
        ``ConfigurationError`` (fresh user, no provider) surfaces as a
        pre-header 400 — the response is JSON, never ``text/event-stream``.
        The novel is created first so the resolver's internal P2
        existence guard does not preempt the cascade error with a 404.
        """
        novel_id = await _create_novel(client, auth_headers)

        resp = await client.post(
            f"/api/v1/analysis/voice-drift/{novel_id}",
            headers=auth_headers,
            json={},
        )

        assert resp.status_code == 400
        assert not resp.headers["content-type"].startswith("text/event-stream")
