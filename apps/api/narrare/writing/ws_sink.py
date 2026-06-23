"""WebSocket sink adapter for the active-turn registry (ADR-052).

Wraps a ``fastapi.WebSocket`` (or any object with an async
``send_json``) to satisfy the
:class:`~narrare.writing.ws_active_turn_registry.SessionTransportSink`
Protocol.

The sink keeps the streaming code transport-agnostic so a future
SSE/MCP adapter can satisfy ``SessionTransportSink`` without changing
the dispatcher (ADR-052 Decision 3).

Send errors on dead sockets are logged and swallowed (RULE-11):
disconnects are expected during stop/cancel, and the registry handles
cancellation — not the sink.  Swallowing prevents a dead-socket
``ConnectionError`` from masking the cancellation path.

See: docs/architecture/decisions/052-session-stop-recovery.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = structlog.get_logger(__name__)

__all__ = ["WebSocketSink"]


class _WebSocketLike(Protocol):
    """Minimal structural type for a WebSocket-like transport."""

    async def send_json(self, data: Mapping[str, object]) -> None: ...


class WebSocketSink:
    """Adapt a WebSocket to the :class:`SessionTransportSink` Protocol.

    Args:
        websocket: The underlying WebSocket (or any object with an
            async ``send_json`` method).
    """

    def __init__(self, websocket: _WebSocketLike) -> None:
        self._websocket = websocket

    async def send_json(self, data: Mapping[str, object]) -> None:
        """Send JSON, swallowing transport errors.

        RULE-11: Send errors on dead sockets are logged at debug level
        and swallowed.  This is deliberate — disconnects are expected
        during stop/cancel, and the registry owns cancellation, not the
        sink.  Propagating the error here would mask the cancellation
        path with a transport-layer exception.
        """
        try:
            await self._websocket.send_json(data)
        except Exception:
            logger.debug(
                "ws_sink_send_failed",
                hint="client likely disconnected; sink swallows transport errors",
            )
