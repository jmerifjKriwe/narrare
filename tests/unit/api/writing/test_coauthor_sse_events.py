"""Unit tests for coauthor_event_stream SSE generator — termination.

Tests the [DONE] termination signal for co-author SSE streaming.
All dependencies are mocked (DI pattern, RULE-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from narrare.writing._coauthor_sse import coauthor_event_stream
from narrare.writing.schemas_coauthor import CoAuthorFocus, CoAuthorRequest
from narrare_core.llm.result import StreamChunk, TokenUsage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USAGE = TokenUsage(prompt_tokens=20, completion_tokens=100, total_tokens=120)

_SELECTION = (
    "This is a sufficiently long selection text that demonstrates the "
    "co-author SSE event streaming flow. It needs to exceed fifty characters "
    "to satisfy Pydantic's min_length constraint on CoAuthorRequest."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request(**kw: Any) -> CoAuthorRequest:
    """Build a valid CoAuthorRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "selection_text": _SELECTION,
        "focus": [CoAuthorFocus.WORD_CHOICE],
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return CoAuthorRequest(**defaults)


class _FakeCoAuthorService:
    """Minimal fake CoAuthorService for SSE testing.

    Wraps a pre-defined list of StreamChunks and returns them
    as an async generator from stream_coauthor().
    """

    def __init__(self, chunks: list[StreamChunk]) -> None:
        self._chunks = chunks

    async def stream_coauthor(
        self,
        chapter_id: Any,
        novel_id: Any,
        user_id: str,
        request: Any,
    ) -> AsyncIterator[StreamChunk]:
        for chunk in self._chunks:
            yield chunk


# ---------------------------------------------------------------------------
# Tests: [DONE] termination
# ---------------------------------------------------------------------------


class TestDoneSignal:
    """Tests for the [DONE] termination event."""

    @pytest.mark.asyncio
    async def test_done_signal_at_end(self) -> None:
        """Always yields [DONE] as the final event."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(text="Some text."),
                StreamChunk(text="", is_final=True, usage=USAGE),
            ]
        )

        last_event: str | None = None
        async for event in coauthor_event_stream(
            service,
            uuid4(),
            uuid4(),
            "user",
            _request(),
        ):
            last_event = event

        assert last_event == "data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_done_signal_even_with_single_chunk(self) -> None:
        """[DONE] is emitted even when there's only one final chunk."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(text="Only chunk.", is_final=True, usage=USAGE),
            ]
        )

        events: list[str] = []
        async for event in coauthor_event_stream(
            service,
            uuid4(),
            uuid4(),
            "user",
            _request(),
        ):
            events.append(event)

        assert len(events) == 2
        assert events[0].startswith("data: ")
        assert events[1] == "data: [DONE]\n\n"
