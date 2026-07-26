"""Unit tests for the ANAL-009 voice-drift SSE route serialization."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from narrare._app.dependencies import SessionDep
from narrare.analysis.router_voice_drift import analyze_voice_drift
from narrare.analysis.schemas_voice_drift import (
    VoiceDriftCharacterResult,
    VoiceDriftEvent,
    VoiceDriftNoProfile,
    VoiceDriftRequest,
)
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Callable


class FakeVoiceDriftService:
    """Fake voice-drift service yielding progress, character_result, no_profile, done."""

    def __init__(
        self,
        result: VoiceDriftCharacterResult,
        no_profile: VoiceDriftNoProfile,
    ) -> None:
        self._result = result
        self._no_profile = no_profile
        self.calls: list[tuple[UUID, UUID, VoiceDriftRequest]] = []

    async def run_stream(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: VoiceDriftRequest,
    ) -> AsyncIterator[VoiceDriftEvent]:
        """Yield a representative successful voice-drift stream."""
        self.calls.append((novel_id, user_id, request))
        yield VoiceDriftEvent(event="progress", progress="Analysing 2 character(s).")
        yield VoiceDriftEvent(event="character_result", result=self._result)
        yield VoiceDriftEvent(event="no_profile", no_profile=self._no_profile)
        yield VoiceDriftEvent(event="done", is_final=True)


async def _collect_sse_payloads(response_body: AsyncIterable[object]) -> list[str]:
    chunks: list[str] = []
    async for chunk in response_body:
        if isinstance(chunk, str):
            chunks.append(chunk)
        elif isinstance(chunk, bytes | bytearray | memoryview):
            chunks.append(bytes(chunk).decode())
        else:  # pragma: no cover - StreamingResponse yields byte-like chunks.
            raise AssertionError(f"Unexpected SSE chunk type: {type(chunk).__name__}")
    return [chunk.removeprefix("data: ").strip() for chunk in chunks]


def _fake_session() -> SessionDep:
    return cast("SessionDep", object())


@pytest.mark.asyncio
async def test_analyze_voice_drift_serializes_progress_result_no_profile_done_and_sentinel() -> (
    None
):
    """SSE route emits JSON progress/character_result/no_profile/done events + [DONE]."""
    novel_id = uuid4()
    user_id = uuid4()
    result = VoiceDriftCharacterResult(
        character_id="char-1",
        character_name="Elena",
        overall_match_score=75.0,
        overall_band="minor",
        drift=VoiceDriftResult(drift_type="evolution", confidence=0.7),
    )
    no_profile = VoiceDriftNoProfile(
        character_name="Marc",
        reason="no_stored_profile",
    )
    service = FakeVoiceDriftService(result, no_profile)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_voice_drift.get_voice_drift_service",
            lambda _session: service,
        )
        stream_response = await analyze_voice_drift(
            novel_id=novel_id,
            request=VoiceDriftRequest(),
            user_id=str(user_id),
            session=_fake_session(),
        )

    payloads = await _collect_sse_payloads(stream_response.body_iterator)
    progress_payload = json.loads(payloads[0])
    result_payload = json.loads(payloads[1])
    no_profile_payload = json.loads(payloads[2])
    done_payload = json.loads(payloads[3])

    assert progress_payload["event"] == "progress"
    assert progress_payload["progress"] == "Analysing 2 character(s)."
    assert result_payload["event"] == "character_result"
    assert result_payload["result"]["character_name"] == "Elena"
    assert result_payload["result"]["drift"]["drift_type"] == "evolution"
    assert no_profile_payload["event"] == "no_profile"
    assert no_profile_payload["no_profile"]["character_name"] == "Marc"
    assert no_profile_payload["no_profile"]["reason"] == "no_stored_profile"
    assert done_payload["event"] == "done"
    assert done_payload["is_final"] is True
    assert payloads[-1] == "[DONE]"
    assert service.calls == [(novel_id, user_id, VoiceDriftRequest())]


@pytest.mark.asyncio
async def test_analyze_voice_drift_emits_error_event_on_failure() -> None:
    """A service failure is surfaced as an in-band ``error`` event (RULE-11)."""

    class FailingService:
        async def run_stream(
            self,
            novel_id: UUID,
            user_id: UUID,
            request: VoiceDriftRequest,
        ) -> AsyncIterator[VoiceDriftEvent]:
            """Raise after streaming starts to exercise in-band SSE errors."""
            raise RuntimeError("boom")
            yield  # pragma: no cover - makes this an async generator

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_voice_drift.get_voice_drift_service",
            lambda _session: FailingService(),
        )
        stream_response = await analyze_voice_drift(
            novel_id=uuid4(),
            request=VoiceDriftRequest(),
            user_id=str(uuid4()),
            session=_fake_session(),
        )

    payloads = await _collect_sse_payloads(stream_response.body_iterator)
    error_payload = json.loads(payloads[0])

    assert error_payload["event"] == "error"
    assert error_payload["is_final"] is True
    assert error_payload["error"] == "Voice-drift analysis failed."
    assert payloads[-1] == "[DONE]"


def test_voice_drift_route_uses_analysis_rate_limiter() -> None:
    """Route metadata keeps the AI analysis rate limiter dependency wired."""
    from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
    from narrare.analysis.router_voice_drift import router

    route = next(
        route
        for route in router.routes
        if getattr(route, "path", "") == "/analysis/voice-drift/{novel_id}"
    )
    dependencies = getattr(route, "dependencies", [])
    dependency_callables: list[Callable[..., object]] = [dep.dependency for dep in dependencies]

    assert AI_ANALYSIS_LIMITER in dependency_callables


def test_voice_drift_route_is_registered_by_app_factory() -> None:
    """App wiring includes the voice-drift router under the API v1 prefix."""
    from narrare._app.main import create_app

    app = create_app(test_mode=True)
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
