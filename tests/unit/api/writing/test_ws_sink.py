"""Tests for WebSocketSink adapter (ADR-052 Phase 1).

Covers:
1. ``WebSocketSink`` satisfies ``SessionTransportSink`` Protocol.
2. ``send_json`` delegates to the underlying websocket.
3. ``send_json`` swallows transport errors (RULE-11 — disconnects are
   expected during stop/cancel; the registry handles cancellation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.writing.ws_active_turn_registry import SessionTransportSink
from narrare.writing.ws_sink import WebSocketSink

if TYPE_CHECKING:
    from collections.abc import Mapping


class FakeWebSocket:
    """Minimal fake WebSocket that records sent messages."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send_json(self, data: Mapping[str, object]) -> None:
        self.sent.append(dict(data))


class BrokenSocket:
    """A websocket whose send_json always raises (simulates dead socket)."""

    async def send_json(self, data: Mapping[str, object]) -> None:
        raise ConnectionError("socket is closed")


class TestWebSocketSink:
    """WebSocketSink transport adapter."""

    def test_satisfies_session_transport_sink_protocol(self) -> None:
        sink = WebSocketSink(FakeWebSocket())
        assert isinstance(sink, SessionTransportSink)

    async def test_send_json_delegates_to_websocket(self) -> None:
        ws = FakeWebSocket()
        sink = WebSocketSink(ws)
        await sink.send_json({"type": "text_chunk", "text": "hello"})
        assert ws.sent == [{"type": "text_chunk", "text": "hello"}]

    async def test_send_json_swallows_transport_errors(self) -> None:
        """Send errors on dead sockets are logged + swallowed (RULE-11).

        Disconnects are expected during stop/cancel — the registry
        handles cancellation, not the sink.
        """
        sink = WebSocketSink(BrokenSocket())
        # Must not raise
        await sink.send_json({"type": "text_chunk", "text": "hello"})
