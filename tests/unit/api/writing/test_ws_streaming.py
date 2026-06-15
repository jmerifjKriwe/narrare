"""Unit tests for the WebSocket streaming DTO adapter.

ADR-045 Decision 6: Stream events are mapped to WebSocket DTOs by a
dedicated adapter (``ws_streaming``), keeping the turn service
transport-agnostic and the handler focused on transport.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.writing.ws_streaming import StreamSendResult, send_stream_chunks
from narrare_core.llm.result import StreamChunk, TokenUsage

if TYPE_CHECKING:
    from collections.abc import Mapping


class _RecordingWebSocket:
    """Records sent JSON messages; satisfies :class:`StreamSender`."""

    def __init__(self) -> None:
        self.sent: list[Mapping[str, object]] = []

    async def send_json(self, data: Mapping[str, object]) -> None:
        self.sent.append(data)


async def _chunk_iter(chunks: list[StreamChunk]):
    """Turn a list into an async iterator."""
    for c in chunks:
        yield c


class TestSendStreamChunks:
    """send_stream_chunks maps StreamChunk → WebSocket DTOs."""

    async def test_sends_text_chunk_for_each_non_final(self) -> None:
        """Each non-final chunk becomes a text_chunk message."""
        ws = _RecordingWebSocket()
        chunks = [
            StreamChunk(text="Hello "),
            StreamChunk(text="world!"),
            StreamChunk(text="", is_final=True, usage=TokenUsage(1, 2, 3)),
        ]

        result = await send_stream_chunks(ws, _chunk_iter(chunks))
        assert isinstance(result, StreamSendResult)

        text_msgs = [m for m in ws.sent if m["type"] == "text_chunk"]
        assert text_msgs[0]["text"] == "Hello "
        assert text_msgs[1]["text"] == "world!"

    async def test_returns_accumulated_full_text(self) -> None:
        """Full text is the concatenation of all non-final chunks."""
        ws = _RecordingWebSocket()
        chunks = [
            StreamChunk(text="Foo "),
            StreamChunk(text="bar"),
            StreamChunk(text="", is_final=True),
        ]

        result = await send_stream_chunks(ws, _chunk_iter(chunks))
        assert isinstance(result, StreamSendResult)
        assert result.full_text == "Foo bar"

    async def test_captures_usage_from_final_chunk(self) -> None:
        """Usage from the final chunk is captured."""
        ws = _RecordingWebSocket()
        usage = TokenUsage(10, 20, 30, provider="test", model="m")
        chunks = [
            StreamChunk(text="hi"),
            StreamChunk(text="", is_final=True, usage=usage),
        ]

        result = await send_stream_chunks(ws, _chunk_iter(chunks))
        assert result.usage is not None
        assert result.usage.total_tokens == 30

    async def test_no_final_chunk_yields_empty_usage(self) -> None:
        """When stream ends without final chunk, usage is None."""
        ws = _RecordingWebSocket()
        chunks = [StreamChunk(text="partial")]

        result = await send_stream_chunks(ws, _chunk_iter(chunks))
        assert result.usage is None
        assert result.full_text == "partial"

    async def test_empty_stream_produces_no_messages(self) -> None:
        """An empty stream sends no text_chunk messages."""
        ws = _RecordingWebSocket()

        result = await send_stream_chunks(ws, _chunk_iter([]))

        assert ws.sent == []
        assert result.full_text == ""
        assert result.usage is None
