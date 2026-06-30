"""Unit tests for the WRITE-010 voice-check SSE route serialization."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from narrare._app.dependencies import SessionDep
from narrare.analysis.router_voice_check import analyze_voice_check
from narrare.analysis.schemas_voice_check import (
    FlaggedLineResponse,
    VoiceCheckResult,
    VoiceCheckStreamEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Callable


class FakeVoiceCheckService:
    """Fake voice-check service yielding progress, result, and done events."""

    def __init__(self, result: VoiceCheckResult) -> None:
        self._result = result
        self.calls: list[tuple[UUID, UUID]] = []

    async def check(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[VoiceCheckStreamEvent]:
        """Yield a representative successful voice-check stream."""
        self.calls.append((chapter_id, user_id))
        yield VoiceCheckStreamEvent(event="progress", progress="Checking 1 character.")
        yield VoiceCheckStreamEvent(event="result", result=self._result)
        yield VoiceCheckStreamEvent(event="done", is_final=True)


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
    # Cast is limited to the router unit boundary: the patched factory ignores it.
    return cast("SessionDep", object())


@pytest.mark.asyncio
async def test_analyze_voice_check_serializes_progress_result_done_and_sentinel() -> None:
    """SSE route emits JSON progress/result/done events and the DONE sentinel."""
    chapter_id = uuid4()
    user_id = uuid4()
    result = VoiceCheckResult(
        character_name="Elena",
        match_score=82.5,
        band="yellow",
        match_judgment="mostly_consistent",
        qualitative_sub_score=80.0,
        metric_delta_subscore=85.0,
        flagged_lines=[
            FlaggedLineResponse(
                quote="Sure it is.",
                reason="Too casual for Elena's established formal register.",
            )
        ],
        has_profile=True,
        n_comparable_metrics=5,
    )
    service = FakeVoiceCheckService(result)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_voice_check.get_voice_check_service",
            lambda _session: service,
        )
        stream_response = await analyze_voice_check(
            chapter_id=chapter_id,
            user_id=str(user_id),
            session=_fake_session(),
        )

    payloads = await _collect_sse_payloads(stream_response.body_iterator)
    progress_payload = json.loads(payloads[0])
    result_payload = json.loads(payloads[1])
    done_payload = json.loads(payloads[2])

    assert progress_payload["event"] == "progress"
    assert progress_payload["progress"] == "Checking 1 character."
    assert result_payload["event"] == "result"
    assert result_payload["result"]["character_name"] == "Elena"
    assert result_payload["result"]["flagged_lines"][0]["quote"] == "Sure it is."
    assert done_payload["event"] == "done"
    assert done_payload["is_final"] is True
    assert payloads[-1] == "[DONE]"
    assert service.calls == [(chapter_id, user_id)]


@pytest.mark.asyncio
async def test_analyze_voice_check_emits_error_event_on_failure() -> None:
    """A service failure is surfaced as an in-band ``error`` event (RULE-11)."""

    class FailingService:
        async def check(
            self,
            chapter_id: UUID,
            user_id: UUID,
        ) -> AsyncIterator[VoiceCheckStreamEvent]:
            """Raise after streaming starts to exercise in-band SSE errors."""
            raise RuntimeError("boom")
            yield  # pragma: no cover - makes this an async generator

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_voice_check.get_voice_check_service",
            lambda _session: FailingService(),
        )
        stream_response = await analyze_voice_check(
            chapter_id=uuid4(),
            user_id=str(uuid4()),
            session=_fake_session(),
        )

    payloads = await _collect_sse_payloads(stream_response.body_iterator)
    error_payload = json.loads(payloads[0])

    assert error_payload["event"] == "error"
    assert error_payload["is_final"] is True
    assert error_payload["error"] == "Voice-check analysis failed."
    assert payloads[-1] == "[DONE]"


def test_voice_check_route_uses_analysis_rate_limiter() -> None:
    """Route metadata keeps the AI analysis rate limiter dependency wired."""
    from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
    from narrare.analysis.router_voice_check import router

    route = next(
        route
        for route in router.routes
        if getattr(route, "path", "") == "/analysis/voice-check/{chapter_id}"
    )
    dependencies = getattr(route, "dependencies", [])
    dependency_callables: list[Callable[..., object]] = [dep.dependency for dep in dependencies]

    assert AI_ANALYSIS_LIMITER in dependency_callables


def test_voice_check_route_is_registered_by_app_factory() -> None:
    """App wiring includes the voice-check router under the API v1 prefix."""
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

    assert "/api/v1/analysis/voice-check/{chapter_id}" in registered_paths
