"""Unit tests for consistency SSE route serialization."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from narrare.consistency.router import stream_consistency_check
from narrare.consistency.schemas import ConsistencyRequest, ConsistencyResponse
from narrare.consistency.stage_schemas import ConsistencyStageEvent
from narrare_core.agents.consistency_types import ConsistencyCheckType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.consistency.checker_service import ConsistencyCheckerService


class FakeConsistencyService:
    """Fake service yielding one stage event and one final response."""

    def __init__(self, response: ConsistencyResponse) -> None:
        self._response = response

    async def ensure_resolved(self) -> None:
        """ADR-086 L13: the SSE route resolves before streaming."""
        return None

    async def stream_check(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: ConsistencyRequest,
    ) -> AsyncIterator[ConsistencyStageEvent | ConsistencyResponse]:
        """Yield a deterministic stage event followed by final response."""
        yield ConsistencyStageEvent(
            stage="extracting_facts",
            status="start",
            progress=0.0,
            message="Extracting facts.",
        )
        yield self._response


@pytest.mark.asyncio
async def test_stream_consistency_check_serializes_stage_and_result() -> None:
    """SSE route emits JSON stage/result events and DONE sentinel."""
    novel_id = uuid4()
    response = ConsistencyResponse(
        novel_id=novel_id,
        chapter_ids=[],
        check_types=[ConsistencyCheckType.CHARACTER],
        issues=[],
        overall_assessment="No issues.",
        analyzed_at="2026-06-12T00:00:00+00:00",
    )
    stream_response = await stream_consistency_check(
        novel_id=novel_id,
        request=ConsistencyRequest(),
        user_id=str(uuid4()),
        # Cast is safe: the route only calls stream_check on the service.
        service=cast("ConsistencyCheckerService", FakeConsistencyService(response)),
    )

    chunks = [
        chunk if isinstance(chunk, str) else bytes(chunk).decode()
        async for chunk in stream_response.body_iterator
    ]
    payloads = [chunk.removeprefix("data: ").strip() for chunk in chunks]

    stage_payload = json.loads(payloads[0])
    result_payload = json.loads(payloads[1])

    assert stage_payload["type"] == "stage"
    assert stage_payload["stage"] == "extracting_facts"
    assert result_payload["type"] == "result"
    assert result_payload["novel_id"] == str(novel_id)
    assert payloads[-1] == "[DONE]"
