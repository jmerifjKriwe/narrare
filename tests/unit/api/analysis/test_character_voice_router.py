"""Unit test for the ANAL-008 character-voice SSE route serialization.

Mirrors ``test_coreference_router.py``: the route is called directly with a
fake service (``get_character_voice_service`` patched) and the SSE body is
consumed to assert the wire format — ``"progress"`` / ``"result"`` / ``"done"``
JSON events and the ``[DONE]`` sentinel.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.analysis.router_character_voice import analyze_character_voice
from narrare.analysis.schemas_character_voice import (
    CharacterVoiceRequest,
    CharacterVoiceResult,
    CharacterVoiceStreamEvent,
)
from narrare_core.kb.schemas.character import VoiceAnalysis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class FakeCharacterVoiceService:
    """Fake service yielding progress + one result + done."""

    def __init__(self, result: CharacterVoiceResult) -> None:
        self._result = result

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[CharacterVoiceStreamEvent]:
        yield CharacterVoiceStreamEvent(event="progress", progress="Profiling 1 character(s).")
        yield CharacterVoiceStreamEvent(event="result", result=self._result)
        yield CharacterVoiceStreamEvent(event="done", is_final=True)


@pytest.mark.asyncio
async def test_analyze_character_voice_serializes_progress_result_done_and_sentinel() -> None:
    """SSE route emits JSON progress/result/done events and the DONE sentinel."""
    novel_id = uuid4()
    result = CharacterVoiceResult(
        character_name="Elena",
        voice_analysis=VoiceAnalysis(formality=0.7, vocabulary_level="complex"),
        distinctiveness_notes="More formal than Marc.",
        kb_entry_id=str(uuid4()),
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_character_voice.get_character_voice_service",
            lambda _session: FakeCharacterVoiceService(result),
        )
        stream_response = await analyze_character_voice(
            novel_id=novel_id,
            request=CharacterVoiceRequest(chapter_ids=None),
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
    assert progress_payload["progress"] == "Profiling 1 character(s)."
    assert result_payload["event"] == "result"
    assert result_payload["result"]["character_name"] == "Elena"
    assert result_payload["result"]["voice_analysis"]["formality"] == 0.7
    assert result_payload["is_final"] is False
    assert done_payload["event"] == "done"
    assert done_payload["is_final"] is True
    assert payloads[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_analyze_character_voice_emits_error_event_on_failure() -> None:
    """A service failure is surfaced as an in-band ``"error"`` event (RULE-11)."""

    class FailingService:
        async def analyze(
            self,
            novel_id: UUID,
            chapter_ids: list[UUID] | None,
            user_id: UUID,
        ) -> AsyncIterator[CharacterVoiceStreamEvent]:
            raise RuntimeError("boom")
            yield  # pragma: no cover - make this an async generator

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_character_voice.get_character_voice_service",
            lambda _session: FailingService(),  # type: ignore[arg-type]
        )
        stream_response = await analyze_character_voice(
            novel_id=uuid4(),
            request=CharacterVoiceRequest(chapter_ids=None),
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
async def test_analyze_character_voice_passes_chapter_ids_to_service() -> None:
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
        ) -> AsyncIterator[CharacterVoiceStreamEvent]:
            captured["novel_id"] = novel_id
            captured["chapter_ids"] = chapter_ids
            yield CharacterVoiceStreamEvent(event="done", is_final=True)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "narrare.analysis.router_character_voice.get_character_voice_service",
            lambda _session: CapturingService(),
        )
        stream_response = await analyze_character_voice(
            novel_id=novel_id,
            request=CharacterVoiceRequest(chapter_ids=[str(chapter_a), str(chapter_b)]),
            user_id=str(uuid4()),
            session=None,  # type: ignore[arg-type]
        )

    # Consume the stream so the async generator runs.
    async for _chunk in stream_response.body_iterator:
        pass

    assert captured["novel_id"] == novel_id
    assert captured["chapter_ids"] == [chapter_a, chapter_b]
