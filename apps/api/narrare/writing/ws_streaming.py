"""WebSocket streaming DTO adapter.

Maps :class:`~narrare_core.llm.result.StreamChunk` instances produced by
the transport-agnostic turn service into WebSocket client DTOs
(``text_chunk`` messages).

ADR-045 Decision 6: Stream events are mapped to transport DTOs by a
dedicated adapter, keeping the turn service transport-agnostic and the
handler focused on accept/loop/route/error transport.

See: ADR-045, CONSTRAINTS.md RULE-06/RULE-12/RULE-13.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from narrare_core.llm.result import StreamChunk, TokenUsage


@dataclass(frozen=True, slots=True)
class StreamSendResult:
    """Result of streaming chunks to a WebSocket transport.

    Attributes:
        full_text: Concatenated text from all non-final chunks.
        usage: Token usage from the final chunk, or ``None`` if the
            stream ended without a final chunk.
    """

    full_text: str
    usage: TokenUsage | None


@runtime_checkable
class StreamSender(Protocol):
    """Minimal transport surface for streaming DTOs over a connection.

    Only ``send_json`` is required: :func:`send_stream_chunks` never reads
    from or closes the connection. Declaring this narrow Protocol (rather
    than the full :class:`fastapi.WebSocket`) follows dependency inversion
    (RULE-03) and keeps the adapter testable with lightweight doubles
    (RULE-12/RULE-13). A real ``fastapi.WebSocket`` satisfies this Protocol.
    """

    async def send_json(self, data: Mapping[str, object]) -> None:
        """Send a JSON-serializable mapping over the transport."""
        ...


async def send_stream_chunks(
    websocket: StreamSender,
    chunks: AsyncIterator[StreamChunk],
) -> StreamSendResult:
    """Stream :class:`StreamChunk` instances to a WebSocket as DTOs.

    Sends each non-final chunk as a ``text_chunk`` message. Accumulates
    the full text and captures usage from the final chunk.

    Does **not** send ``text_done`` — the caller is responsible for
    persisting the assistant message and sending the completion DTO,
    since that involves session state outside the streaming concern.

    Args:
        websocket: A :class:`StreamSender` (any object with an async
            ``send_json`` method, e.g. ``fastapi.WebSocket``) to send DTOs to.
        chunks: An async iterator of :class:`StreamChunk` from the turn
            service or registry.

    Returns:
        :class:`StreamSendResult` with the accumulated text and usage.
    """
    accumulated: list[str] = []
    final_usage: TokenUsage | None = None

    async for chunk in chunks:
        if chunk.is_final:
            final_usage = chunk.usage
            break
        accumulated.append(chunk.text)
        await websocket.send_json({"type": "text_chunk", "text": chunk.text})

    return StreamSendResult(
        full_text="".join(accumulated),
        usage=final_usage,
    )
