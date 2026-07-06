"""Active-turn registry for WebSocket writing sessions (ADR-052).

Holds the live ``asyncio.Task`` and transport-agnostic
:class:`SessionTransportSink` for the single active streaming turn per
session.  Cancellation propagates into the in-flight ``await
__anext__()`` of the model stream via ``Task.cancel()`` (RULE-20).

Design notes
------------

- **In-process by design.**  ``asyncio.Task`` handles are live objects
  that cannot be serialized.  Multi-worker deployments need a
  Redis-backed metadata store PLUS an in-process map for the live cancel
  path (ADR-052 Review Trigger #1).
- **One active turn per session.**  Concurrent ``user_direction``
  messages are rejected with a ``busy`` error by the dispatcher before
  reaching the registry.
- **Transport-agnostic.**  The registry stores a
  :class:`SessionTransportSink`, not a WebSocket — so SSE/MCP transports
  can reuse the same registry.

See: docs/architecture/decisions/ADR-052-session-stop-recovery.md
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Mapping

logger = structlog.get_logger(__name__)

__all__ = [
    "ActiveTurn",
    "ActiveTurnRegistry",
    "CancelResult",
    "NullSessionTransportSink",
    "SessionTransportSink",
]


# ---------------------------------------------------------------------------
# Transport-agnostic sink Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SessionTransportSink(Protocol):
    """Minimal transport surface for pushing messages to a client.

    Distinct from :class:`~narrare.writing.ws_streaming.StreamSender`:
    the sink is **session-scoped, not connection-scoped**.  It can be
    rebound to a new WebSocket on reattach without restarting the turn
    (ADR-052 Decision 3).

    A :class:`~narrare.writing.ws_sink.WebSocketSink` wrapping a real
    ``fastapi.WebSocket`` satisfies this Protocol.
    """

    async def send_json(self, data: Mapping[str, object]) -> None:
        """Send a JSON-serializable mapping over the transport."""
        ...


class NullSessionTransportSink:
    """A sink that discards all sends.

    Used as a default when no client is connected (e.g. after a
    disconnect before reattach, or in tests).
    """

    async def send_json(self, data: Mapping[str, object]) -> None:
        """Discard the data silently."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ActiveTurn:
    """The registered active streaming turn for one session.

    Attributes:
        invocation_id: The LLM invocation identifier for this turn.
        task: The ``asyncio.Task`` running the streaming turn.
            ``Task.cancel()`` propagates ``CancelledError`` into the
            blocked ``await __anext__()`` of the model stream.
        sink: The transport-agnostic sink for pushing DTOs to the client.
        started_at: ``time.monotonic()`` when the turn was registered.
    """

    invocation_id: str
    task: asyncio.Task[str | None]
    sink: SessionTransportSink
    started_at: float = field(default_factory=time.monotonic)


@dataclass(frozen=True, slots=True)
class CancelResult:
    """Result of cancelling an active turn.

    Attributes:
        cancelled: ``True`` if a live task was found and cancelled.
        partial_prose: The partial prose text associated with the cancel
            (read from :class:`SessionTurnStateStore` by the caller).
    """

    cancelled: bool
    partial_prose: str


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ActiveTurnRegistry:
    """Process-local registry of the single active turn per session.

    All methods are synchronous — the registry performs no I/O.
    """

    def __init__(self) -> None:
        self._turns: dict[str, ActiveTurn] = {}

    def register(
        self,
        session_id: str,
        invocation_id: str,
        *,
        task: asyncio.Task[str | None],
        sink: SessionTransportSink,
    ) -> None:
        """Register the active turn for ``session_id``.

        If a turn was already registered (re-entrancy), the previous
        task is **not** cancelled here — the caller is expected to have
        finalized/unregistered it first.  The new turn replaces the old
        entry.
        """
        self._turns[session_id] = ActiveTurn(
            invocation_id=invocation_id,
            task=task,
            sink=sink,
        )
        logger.debug(
            "active_turn_registered",
            session_id=session_id,
            invocation_id=invocation_id,
        )

    def get(self, session_id: str) -> ActiveTurn | None:
        """Return the active turn, or ``None`` if none is registered."""
        return self._turns.get(session_id)

    def get_sink(self, session_id: str) -> SessionTransportSink:
        """Return the sink for the active turn, or a NullSessionTransportSink."""
        turn = self._turns.get(session_id)
        if turn is None:
            return NullSessionTransportSink()
        return turn.sink

    def rebind_sink(
        self,
        session_id: str,
        sink: SessionTransportSink,
    ) -> bool:
        """Rebind the sink for an active turn (ADR-052 Phase 2 reattach).

        Returns ``True`` if a turn was found and rebound, ``False``
        otherwise.
        """
        turn = self._turns.get(session_id)
        if turn is None:
            return False
        turn.sink = sink
        logger.debug(
            "active_turn_sink_rebound",
            session_id=session_id,
            invocation_id=turn.invocation_id,
        )
        return True

    def cancel(
        self,
        session_id: str,
        *,
        partial_prose: str,
    ) -> CancelResult:
        """Pop the active turn and cancel its task.

        ``Task.cancel()`` propagates ``CancelledError`` into the blocked
        ``await __anext__()`` of the model stream (RULE-20).

        Returns ``CancelResult(cancelled=False, ...)`` if no active turn
        exists for ``session_id``.
        """
        turn = self._turns.pop(session_id, None)
        if turn is None:
            return CancelResult(cancelled=False, partial_prose="")
        turn.task.cancel()
        logger.info(
            "active_turn_cancelled",
            session_id=session_id,
            invocation_id=turn.invocation_id,
        )
        return CancelResult(cancelled=True, partial_prose=partial_prose)

    def unregister(self, session_id: str) -> None:
        """Remove a completed turn without cancelling it."""
        turn = self._turns.pop(session_id, None)
        if turn is not None:
            logger.debug(
                "active_turn_unregistered",
                session_id=session_id,
                invocation_id=turn.invocation_id,
            )
