"""Unit tests for the ANAL-007 author-voice SSE route serialization.

Mirrors ``test_character_voice_router.py``: the route is called directly with
a fake service (``get_author_voice_service`` patched) and the SSE body is
consumed to assert the wire format — ``"progress"`` / ``"result"`` /
``"done"`` JSON events and the ``[DONE]`` sentinel.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import pytest

from narrare.analysis.router_author_voice import analyze_author_voice
from narrare.analysis.schemas_author_voice import (
    AuthorVoiceRequest,
    AuthorVoiceResult,
    AuthorVoiceStreamEvent,
)
from narrare_core.profiles.author_voice import AuthorVoiceProfile

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _service_factory(service: Any) -> Any:
    """Typed async factory closure for MonkeyPatch.setattr (pyright strict).

    Mirrors the integration-test helper: a named closure with an explicit
    ``Any`` annotation satisfies the checker where a lambda would not.
    Async since Task 2b — the router awaits the factory (per-user model
    routing resolution happens inside).
    """

    async def _factory(**_kwargs: Any) -> Any:
        return service

    return _factory


def _make_profile() -> AuthorVoiceProfile:
    """Build a profile for the result payload."""
    from narrare_core.schemas.voice import VoiceAnalysis

    return AuthorVoiceProfile(
        voice_analysis=VoiceAnalysis(
            formality=0.7,
            vocabulary_level="complex",
            sentence_profile="long",
            emotional_range="expressive",
        ),
        author_examples=["The wind moved through the long grass."],
    )


class FakeAuthorVoiceService:
    """Fake service yielding progress + one result + done."""

    def __init__(self, result: AuthorVoiceResult) -> None:
        self._result = result

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[AuthorVoiceStreamEvent]:
        yield AuthorVoiceStreamEvent(
            event="progress", progress="Analysing author voice across 3 chapter(s)."
        )
        yield AuthorVoiceStreamEvent(event="result", result=self._result)
        yield AuthorVoiceStreamEvent(event="done", is_final=True)


@pytest.mark.asyncio
async def test_analyze_author_voice_serializes_progress_result_done_and_sentinel() -> None:
    """SSE route emits JSON progress/result/done events and the DONE sentinel."""
    novel_id = uuid4()
    result = AuthorVoiceResult(novel_id=str(novel_id), profile=_make_profile())

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_author_voice.get_author_voice_service",
            _service_factory(FakeAuthorVoiceService(result)),
        )
        stream_response = await analyze_author_voice(
            novel_id=novel_id,
            request=AuthorVoiceRequest(chapter_ids=None),
            user_id=str(uuid4()),
            session=None,  # type: ignore[arg-type]
        )

    chunks = [
        chunk if isinstance(chunk, str) else bytes(chunk).decode()
        async for chunk in stream_response.body_iterator
    ]
    payloads = [chunk.removeprefix("data: ").strip() for chunk in chunks]

    progress_payload = json.loads(payloads[0])
    result_payload = json.loads(payloads[1])
    done_payload = json.loads(payloads[2])

    assert progress_payload["event"] == "progress"
    assert progress_payload["progress"] == "Analysing author voice across 3 chapter(s)."
    assert result_payload["event"] == "result"
    assert result_payload["result"]["novel_id"] == str(novel_id)
    assert result_payload["result"]["profile"]["voice_analysis"]["formality"] == 0.7
    assert result_payload["is_final"] is False
    assert done_payload["event"] == "done"
    assert done_payload["is_final"] is True
    assert payloads[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_analyze_author_voice_emits_error_event_on_failure() -> None:
    """A service failure is surfaced as an in-band ``"error"`` event (RULE-11)."""

    class FailingService:
        async def analyze(
            self,
            novel_id: UUID,
            chapter_ids: list[UUID] | None,
            user_id: UUID,
        ) -> AsyncIterator[AuthorVoiceStreamEvent]:
            raise RuntimeError("boom")
            yield  # pragma: no cover - make this an async generator

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_author_voice.get_author_voice_service",
            _service_factory(FailingService()),  # type: ignore[arg-type]
        )
        stream_response = await analyze_author_voice(
            novel_id=uuid4(),
            request=AuthorVoiceRequest(chapter_ids=None),
            user_id=str(uuid4()),
            session=None,  # type: ignore[arg-type]
        )

    chunks = [
        chunk if isinstance(chunk, str) else bytes(chunk).decode()
        async for chunk in stream_response.body_iterator
    ]
    payloads = [chunk.removeprefix("data: ").strip() for chunk in chunks]

    error_payload = json.loads(payloads[0])
    assert error_payload["event"] == "error"
    assert error_payload["is_final"] is True
    assert error_payload["error"]
    assert payloads[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_analyze_author_voice_passes_chapter_ids_to_service() -> None:
    """Explicit chapter_ids are parsed and forwarded to the service."""
    novel_id = uuid4()
    chapter_a = uuid4()
    chapter_b = uuid4()
    captured: dict[str, object] = {}

    class CapturingService:
        async def analyze(
            self,
            novel_id: UUID,
            chapter_ids: list[UUID] | None,
            user_id: UUID,
        ) -> AsyncIterator[AuthorVoiceStreamEvent]:
            captured["novel_id"] = novel_id
            captured["chapter_ids"] = chapter_ids
            yield AuthorVoiceStreamEvent(event="done", is_final=True)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_author_voice.get_author_voice_service",
            _service_factory(CapturingService()),
        )
        stream_response = await analyze_author_voice(
            novel_id=novel_id,
            request=AuthorVoiceRequest(chapter_ids=[str(chapter_a), str(chapter_b)]),
            user_id=str(uuid4()),
            session=None,  # type: ignore[arg-type]
        )

    # Consume the stream so the async generator runs.
    async for _chunk in stream_response.body_iterator:
        pass

    assert captured["novel_id"] == novel_id
    assert captured["chapter_ids"] == [chapter_a, chapter_b]
