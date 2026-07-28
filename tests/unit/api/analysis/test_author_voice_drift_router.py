"""Unit tests for the ANAL-009 Phase 2B author-voice-drift SSE route
serialization.

Mirrors ``test_voice_drift_router.py`` (Phase 1), adapted for the singular
narrator result event (no per-character loop). Exercises the FastAPI route
function directly with a fake service patched in — no app/auth dependency
container needed (that is covered by the integration test).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest

from narrare._app.dependencies import SessionDep
from narrare.analysis.router_author_voice_drift import analyze_author_voice_drift
from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftEvent,
    AuthorVoiceDriftNoProfile,
    AuthorVoiceDriftRequest,
    AuthorVoiceDriftResult,
)
from narrare_core.agents.character_voice_drift_types import VoiceDriftResult

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Callable


def _factory(service: Any) -> Callable[[Any], Any]:
    """Typed factory closure for MonkeyPatch.setattr (pyright-strict safe).

    A bare ``lambda _session: service`` flags ``reportUnknownArgumentType``
    under pyright strict; a named closure with explicit ``Any`` annotations
    satisfies the checker while preserving the runtime behaviour (the DI
    factory ignores its session argument).
    """

    def _get_service(_session: Any) -> Any:
        return service

    return _get_service


class FakeAuthorVoiceDriftService:
    """Fake author-voice-drift service yielding progress, result, done."""

    def __init__(self, result: AuthorVoiceDriftResult) -> None:
        self._result = result
        self.calls: list[tuple[UUID, UUID, AuthorVoiceDriftRequest]] = []

    async def run_stream(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AsyncIterator[AuthorVoiceDriftEvent]:
        """Yield a representative successful author-voice-drift stream."""
        self.calls.append((novel_id, user_id, request))
        yield AuthorVoiceDriftEvent(
            event="progress", progress="Analysing author-voice drift across 2 chapter(s)."
        )
        yield AuthorVoiceDriftEvent(event="result", result=self._result)
        yield AuthorVoiceDriftEvent(event="done", is_final=True)


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
async def test_route_serializes_progress_result_done_and_sentinel() -> None:
    """SSE route emits JSON progress/result/done events + [DONE]."""
    novel_id = uuid4()
    user_id = uuid4()
    result = AuthorVoiceDriftResult(
        novel_id=str(novel_id),
        overall_match_score=75.0,
        overall_band="minor",
        drift=VoiceDriftResult(drift_type="evolution", confidence=0.7),
    )
    service = FakeAuthorVoiceDriftService(result)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_author_voice_drift.get_author_voice_drift_service",
            lambda _session: service,
        )
        stream_response = await analyze_author_voice_drift(
            novel_id=novel_id,
            request=AuthorVoiceDriftRequest(),
            user_id=str(user_id),
            session=_fake_session(),
        )

    payloads = await _collect_sse_payloads(stream_response.body_iterator)
    progress_payload = json.loads(payloads[0])
    result_payload = json.loads(payloads[1])
    done_payload = json.loads(payloads[2])

    assert progress_payload["event"] == "progress"
    assert "author-voice drift" in progress_payload["progress"]
    assert result_payload["event"] == "result"
    assert result_payload["result"]["novel_id"] == str(novel_id)
    assert result_payload["result"]["drift"]["drift_type"] == "evolution"
    assert done_payload["event"] == "done"
    assert done_payload["is_final"] is True
    assert payloads[-1] == "[DONE]"
    assert service.calls == [(novel_id, user_id, AuthorVoiceDriftRequest())]


@pytest.mark.asyncio
async def test_route_serializes_no_profile_event() -> None:
    """The no_profile graceful skip serializes through the SSE route."""

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

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_author_voice_drift.get_author_voice_drift_service",
            lambda _session: NoProfileService(),
        )
        stream_response = await analyze_author_voice_drift(
            novel_id=uuid4(),
            request=AuthorVoiceDriftRequest(),
            user_id=str(uuid4()),
            session=_fake_session(),
        )

    payloads = await _collect_sse_payloads(stream_response.body_iterator)
    no_profile_payload = json.loads(payloads[0])
    done_payload = json.loads(payloads[1])

    assert no_profile_payload["event"] == "no_profile"
    assert no_profile_payload["no_profile"]["reason"] == "no_stored_profile"
    assert done_payload["event"] == "done"
    assert payloads[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_route_emits_error_event_on_failure() -> None:
    """A service failure is surfaced as an in-band ``error`` event (RULE-11)."""

    class FailingService:
        async def run_stream(
            self,
            novel_id: UUID,
            user_id: UUID,
            request: AuthorVoiceDriftRequest,
        ) -> AsyncIterator[AuthorVoiceDriftEvent]:
            """Raise after streaming starts to exercise in-band SSE errors."""
            raise RuntimeError("boom")
            yield  # pragma: no cover - makes this an async generator

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_author_voice_drift.get_author_voice_drift_service",
            lambda _session: FailingService(),
        )
        stream_response = await analyze_author_voice_drift(
            novel_id=uuid4(),
            request=AuthorVoiceDriftRequest(),
            user_id=str(uuid4()),
            session=_fake_session(),
        )

    payloads = await _collect_sse_payloads(stream_response.body_iterator)
    error_payload = json.loads(payloads[0])

    assert error_payload["event"] == "error"
    assert error_payload["is_final"] is True
    assert error_payload["error"] == "Author-voice-drift analysis failed."
    assert payloads[-1] == "[DONE]"


def test_route_uses_analysis_rate_limiter() -> None:
    """Route metadata keeps the AI analysis rate limiter dependency wired."""
    from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
    from narrare.analysis.router_author_voice_drift import router

    route = next(
        route
        for route in router.routes
        if getattr(route, "path", "") == "/analysis/author-voice-drift/{novel_id}"
    )
    dependencies = getattr(route, "dependencies", [])
    dependency_callables: list[Callable[..., object]] = [dep.dependency for dep in dependencies]

    assert AI_ANALYSIS_LIMITER in dependency_callables


def test_route_is_registered_by_app_factory() -> None:
    """App wiring includes the author-voice-drift router under the API v1 prefix."""
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

    assert "/api/v1/analysis/author-voice-drift/{novel_id}" in registered_paths
