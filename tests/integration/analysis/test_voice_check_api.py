"""Integration tests for the WRITE-010 voice-check SSE API endpoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.analysis.schemas_voice_check import VoiceCheckResult, VoiceCheckStreamEvent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from httpx import AsyncClient


class FakeVoiceCheckService:
    """Fake service for app-level SSE routing tests."""

    async def check(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[VoiceCheckStreamEvent]:
        """Yield one result and a terminal done event."""
        yield VoiceCheckStreamEvent(event="progress", progress="Checking voice consistency.")
        yield VoiceCheckStreamEvent(
            event="result",
            result=VoiceCheckResult(character_name="Elena", match_score=90.0, band="green"),
        )
        yield VoiceCheckStreamEvent(event="done", is_final=True)


def _sse_payloads(text: str) -> list[str]:
    return [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: ")]


class TestVoiceCheckAPI:
    """Voice-check streaming endpoint."""

    async def test_voice_check_streams_events_and_done_sentinel(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """POST streams progress/result/done JSON events plus [DONE]."""
        with pytest.MonkeyPatch.context() as mp:

            async def _fake_factory(**_kwargs: object) -> FakeVoiceCheckService:
                return FakeVoiceCheckService()

            mp.setattr(
                "narrare.analysis.router_voice_check.get_voice_check_service",
                _fake_factory,
            )
            resp = await client.post(
                f"/api/v1/analysis/voice-check/{uuid4()}",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        payloads = _sse_payloads(resp.text)
        progress_payload = json.loads(payloads[0])
        result_payload = json.loads(payloads[1])
        done_payload = json.loads(payloads[2])

        assert progress_payload["event"] == "progress"
        assert result_payload["event"] == "result"
        assert result_payload["result"]["character_name"] == "Elena"
        assert done_payload["event"] == "done"
        assert payloads[-1] == "[DONE]"

    async def test_voice_check_without_auth_returns_401(self, client: AsyncClient) -> None:
        """POST without auth headers is rejected by the app auth dependency."""
        resp = await client.post(f"/api/v1/analysis/voice-check/{uuid4()}")

        assert resp.status_code == 401

    async def test_voice_check_invalid_chapter_id_returns_422(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Invalid UUID path parameters fail request validation."""
        resp = await client.post(
            "/api/v1/analysis/voice-check/not-a-uuid",
            headers=auth_headers,
        )

        assert resp.status_code == 422

    async def test_voice_check_route_is_registered_on_app(self, app: FastAPI) -> None:
        """The voice-check router is included under the API v1 analysis prefix."""
        registered_paths: set[str] = set()
        for route in app.routes:
            original_router = getattr(route, "original_router", None)
            include_context = getattr(route, "include_context", None)
            if original_router is None or include_context is None:
                continue
            prefix = getattr(include_context, "prefix", "")
            for child_route in original_router.routes:
                registered_paths.add(f"{prefix}{getattr(child_route, 'path', '')}")

        assert "/api/v1/analysis/voice-check/{chapter_id}" in registered_paths
