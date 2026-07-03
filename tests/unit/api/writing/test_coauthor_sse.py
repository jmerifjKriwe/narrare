"""Unit tests for coauthor_event_stream SSE generator.

Tests the SSE event stream formatting for co-author streaming responses.
All dependencies are mocked (DI pattern, RULE-07).

Covers:
1. context_meta event (CR-07) — first chunk with KB context data
2. Text chunk events — correctly formatted SSE data
3. Final chunk — includes is_final, usage, and diff metadata
4. [DONE] termination signal
5. context_meta on final chunk merged into data (not separate event)
"""

from __future__ import annotations

import json
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


def _parse_sse(data: str) -> dict[str, Any]:
    """Parse an SSE ``data:`` line into a dict."""
    return json.loads(data[len("data: ") :].strip())


# ---------------------------------------------------------------------------
# Tests: context_meta event
# ---------------------------------------------------------------------------


class TestContextMetaEvent:
    """Tests for CR-07 context metadata event emission."""

    @pytest.mark.asyncio
    async def test_context_meta_yields_separate_event(self) -> None:
        """First chunk with context_meta yields a context_meta SSE event."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(text="", context_meta={"sources": ["ch1"], "kb_entries": 3}),
                StreamChunk(text="Revised text."),
                StreamChunk(text="", is_final=True, usage=USAGE),
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

        # Event structure: context_meta + text + final + [DONE]
        assert len(events) == 4

        first = _parse_sse(events[0])
        assert first["type"] == "context_meta"
        assert first["sources"] == ["ch1"]
        assert first["kb_entries"] == 3

    @pytest.mark.asyncio
    async def test_context_meta_not_emitted_for_final_chunk(self) -> None:
        """context_meta on final chunk is merged into data, not separate event."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(text="Pre-final."),
                StreamChunk(
                    text="Final.",
                    is_final=True,
                    usage=USAGE,
                    context_meta={
                        "changes": [{"original": "x", "revised": "y"}],
                        "total_changes": 1,
                        "has_changes": True,
                        "reasoning": "Better",
                        "request_id": "req-1",
                    },
                ),
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

        # Pre-final + final (with embedded meta) + [DONE]
        assert len(events) == 3

        final = _parse_sse(events[1])
        assert final["text"] == "Final."
        assert final["is_final"] is True
        assert final["total_changes"] == 1
        assert final["has_changes"] is True
        # Should NOT have type=context_meta marker
        assert "type" not in final or final.get("type") != "context_meta"

    @pytest.mark.asyncio
    async def test_context_meta_with_non_final_only_triggers_event(self) -> None:
        """context_meta only triggers the context_meta event when is_final=False."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(
                    text="",
                    context_meta={"value": 42},
                    is_final=False,
                ),
                StreamChunk(text="Content."),
                StreamChunk(
                    text="",
                    is_final=True,
                    usage=USAGE,
                    context_meta={"changes": [], "total_changes": 0, "has_changes": False},
                ),
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

        # context_meta + text + final + [DONE]
        assert len(events) == 4

        # First event: context_meta
        first = _parse_sse(events[0])
        assert first["type"] == "context_meta"
        assert first["value"] == 42

        # Second event: normal text
        second = _parse_sse(events[1])
        assert second["text"] == "Content."

        # Third event: final with changes data (not context_meta type)
        third = _parse_sse(events[2])
        assert third["is_final"] is True
        assert third["has_changes"] is False


# ---------------------------------------------------------------------------
# Tests: text chunk events
# ---------------------------------------------------------------------------


class TestTextChunks:
    """Tests for normal text chunk SSE events."""

    @pytest.mark.asyncio
    async def test_text_chunk_has_correct_format(self) -> None:
        """Normal text chunk yields correctly formatted SSE data."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(text="Hello world."),
                StreamChunk(text="", is_final=True, usage=USAGE),
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

        assert len(events) == 3  # text + final + [DONE]

        text_event = _parse_sse(events[0])
        assert text_event["text"] == "Hello world."
        assert "is_final" not in text_event
        assert "usage" not in text_event

    @pytest.mark.asyncio
    async def test_multiple_text_chunks_yielded_in_order(self) -> None:
        """Multiple text chunks maintain order in SSE events."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(text="First. "),
                StreamChunk(text="Second. "),
                StreamChunk(text="Third."),
                StreamChunk(text="", is_final=True, usage=USAGE),
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

        # 3 text + 1 final + 1 [DONE] = 5
        assert len(events) == 5

        for i, expected in enumerate(["First. ", "Second. ", "Third."]):
            chunk = _parse_sse(events[i])
            assert chunk["text"] == expected
            assert "is_final" not in chunk


# ---------------------------------------------------------------------------
# Tests: final chunk with usage and diff metadata
# ---------------------------------------------------------------------------


class TestFinalChunk:
    """Tests for the final chunk with is_final, usage, and diff metadata."""

    @pytest.mark.asyncio
    async def test_final_chunk_includes_usage(self) -> None:
        """Final chunk includes usage information."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(text="Final text.", is_final=True, usage=USAGE),
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

        assert len(events) == 2  # final + [DONE]

        final = _parse_sse(events[0])
        assert final["text"] == "Final text."
        assert final["is_final"] is True
        assert final["usage"] == {
            "prompt_tokens": 20,
            "completion_tokens": 100,
            "total_tokens": 120,
        }

    @pytest.mark.asyncio
    async def test_final_chunk_includes_diff_metadata(self) -> None:
        """Final chunk embeds changes, total_changes, has_changes, reasoning."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(
                    text="",
                    is_final=True,
                    usage=USAGE,
                    context_meta={
                        "changes": [{"original": "good", "revised": "excellent"}],
                        "total_changes": 1,
                        "has_changes": True,
                        "reasoning": "Better word choice",
                        "request_id": "req-123",
                    },
                ),
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

        final = _parse_sse(events[0])
        assert final["is_final"] is True
        assert final["total_changes"] == 1
        assert final["has_changes"] is True
        assert final["reasoning"] == "Better word choice"
        assert "changes" in final
        assert len(final["changes"]) == 1
        assert final["changes"][0]["original"] == "good"

    @pytest.mark.asyncio
    async def test_final_chunk_without_usage_none_omitted(self) -> None:
        """When usage is None, usage key is omitted from final event."""
        service = _FakeCoAuthorService(
            [
                StreamChunk(text="Done.", is_final=True, usage=None),
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

        final = _parse_sse(events[0])
        assert final["is_final"] is True
        assert "usage" not in final
