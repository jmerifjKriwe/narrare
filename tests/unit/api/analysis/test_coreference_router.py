"""Unit test for the ANAL-005 coreference SSE route serialization.

Mirrors ``tests/unit/api/consistency/test_router_sse.py``: the route is
called directly with a fake service (``get_coreference_service`` patched)
and the SSE body is consumed to assert the wire format — a ``"result"``
JSON event, a ``"done"`` JSON event, and the ``[DONE]`` sentinel.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from narrare.analysis.router_coreference import analyze_coreference
from narrare.analysis.schemas_coreference import (
    CoreferenceResponse,
    CoreferenceStreamEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class FakeCoreferenceService:
    """Fake service yielding one result event then a done event."""

    def __init__(self, response: CoreferenceResponse) -> None:
        self._response = response

    async def analyze(
        self,
        chapter_id: UUID,
        user_id: UUID,
    ) -> AsyncIterator[CoreferenceStreamEvent]:
        """Yield a result event followed by a terminal done event."""
        yield CoreferenceStreamEvent(event="result", result=self._response)
        yield CoreferenceStreamEvent(event="done", is_final=True)


@pytest.mark.asyncio
async def test_analyze_coreference_serializes_result_done_and_sentinel() -> None:
    """SSE route emits JSON result/done events and the DONE sentinel."""
    chapter_id = uuid4()
    response = CoreferenceResponse(
        chapter_id=str(chapter_id),
        clarity_score=78.0,
        summary="Most pronouns resolve clearly.",
        resolutions=[],
        character_mentions=[],
    )

    with pytest.MonkeyPatch.context() as mp:

        async def _fake_factory(**_kwargs: object) -> FakeCoreferenceService:
            return FakeCoreferenceService(response)

        mp.setattr(
            "narrare.analysis.router_coreference.get_coreference_service",
            _fake_factory,
        )
        stream_response = await analyze_coreference(
            chapter_id=chapter_id,
            user_id=str(uuid4()),
            session=None,  # type: ignore[arg-type]
        )

    chunks = [
        chunk if isinstance(chunk, str) else bytes(chunk).decode()
        async for chunk in stream_response.body_iterator
    ]
    payloads = [chunk.removeprefix("data: ").strip() for chunk in chunks]

    result_payload = json.loads(payloads[0])
    done_payload = json.loads(payloads[1])

    assert result_payload["event"] == "result"
    assert result_payload["result"]["chapter_id"] == str(chapter_id)
    assert result_payload["result"]["clarity_score"] == 78.0
    assert result_payload["is_final"] is False
    assert done_payload["event"] == "done"
    assert done_payload["is_final"] is True
    assert payloads[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_analyze_coreference_emits_error_event_on_failure() -> None:
    """A service failure is surfaced as an in-band ``"error"`` event (RULE-11)."""

    class FailingService:
        async def analyze(
            self, chapter_id: UUID, user_id: UUID
        ) -> AsyncIterator[CoreferenceStreamEvent]:
            raise RuntimeError("boom")
            yield  # pragma: no cover - make this an async generator
            # The ``yield`` above is unreachable; it exists only so Python
            # treats ``analyze`` as an async generator.

    with pytest.MonkeyPatch.context() as mp:

        async def _failing_factory(**_kwargs: object) -> FailingService:
            return FailingService()

        mp.setattr(
            "narrare.analysis.router_coreference.get_coreference_service",
            _failing_factory,  # type: ignore[arg-type]
        )
        stream_response = await analyze_coreference(
            chapter_id=uuid4(),
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
