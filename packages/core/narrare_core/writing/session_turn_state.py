"""In-process registry of the active streaming turn per writing session (ADR-052).

The :class:`SessionTurnStateStore` holds the *hot* partial-prose state for a
streaming turn: the invocation id, the monotonically increasing chunk
sequence number, and the accumulated partial text.  It is the source of
truth that ``stop_generation`` reads to surface preserved prose, and that
``reattach_session`` reads to populate ``active_partial_prose`` on a
recovered :class:`SessionState`.

Design notes
------------

- **In-process by design.**  This store keeps state in a plain ``dict``; it
  performs no I/O and has no cache dependency (RULE-08).  A future
  Redis-backed implementation satisfying the same surface is called out as
  ADR-052 Review Trigger #1 (multi-worker deployments).
- **Async surface.**  Every method is ``async`` even though the in-memory
  implementation does not await, so a Redis-backed replacement can satisfy
  the same Protocol without callers changing.
- **Persistence boundary.**  This store does NOT write to
  :class:`SessionCacheProtocol`.  The backend control service is
  responsible for persisting the final snapshot onto :class:`SessionState`
  via the :class:`SessionManager` when a turn completes or is cancelled.

See: docs/architecture/decisions/ADR-052-session-stop-recovery.md (ADR-052)
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from narrare_core.writing._enums import StreamStatus

__all__ = [
    "ActiveTurnSnapshot",
    "SessionTurnStateStore",
]

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Snapshot returned to callers (immutable view of the live turn)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ActiveTurnSnapshot:
    """Immutable view of the active turn for a session.

    Returned by :meth:`SessionTurnStateStore.register_active_turn` and
    :meth:`SessionTurnStateStore.get_active_snapshot`.
    """

    invocation_id: str
    sequence: int
    partial_prose: str


# ---------------------------------------------------------------------------
# Internal mutable turn record
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _ActiveTurn:
    """Mutable working record of a streaming turn."""

    invocation_id: str
    sequence: int = 0
    partial_prose: str = ""


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class SessionTurnStateStore:
    """In-process registry of the active streaming turn per session.

    All methods are async so a future Redis-backed implementation can
    satisfy the same surface without caller changes (ADR-052 RT#1).
    """

    def __init__(self) -> None:
        self._turns: dict[str, _ActiveTurn] = {}

    async def register_active_turn(
        self,
        session_id: str,
        invocation_id: str,
    ) -> ActiveTurnSnapshot:
        """Register a new active turn for ``session_id``.

        Resets the sequence counter and partial prose.  If a turn was
        already registered for this session (e.g. re-entrancy), it is
        replaced — the caller is expected to have finalized/cancelled the
        previous turn.
        """
        turn = _ActiveTurn(invocation_id=invocation_id)
        self._turns[session_id] = turn
        logger.debug(
            "active_turn_registered",
            session_id=session_id,
            invocation_id=invocation_id,
        )
        return self._snapshot(turn)

    async def record_chunk(self, session_id: str, text: str) -> int:
        """Append ``text`` to the partial prose and increment the sequence.

        Returns the new sequence number after this chunk, or ``0`` if there
        is no active turn for ``session_id`` (no-op).
        """
        turn = self._turns.get(session_id)
        if turn is None:
            return 0
        turn.partial_prose += text
        turn.sequence += 1
        return turn.sequence

    async def finalize_turn(
        self,
        session_id: str,
        final_text: str = "",
        status: StreamStatus = StreamStatus.COMPLETED,
    ) -> str:
        """Finalize the active turn, returning the preserved prose.

        If ``final_text`` is non-empty, it is treated as the authoritative
        full output from the LLM and returned in place of the accumulated
        partial.  Otherwise the accumulated partial prose is returned.

        The turn is removed from the registry regardless.  ``status`` is
        accepted as an observability hook (the caller logs / persists it via
        the session manager) — it does not affect the return value.

        Returns an empty string if there is no active turn.
        """
        turn = self._turns.pop(session_id, None)
        if turn is None:
            return ""
        preserved = final_text if final_text else turn.partial_prose
        logger.debug(
            "active_turn_finalized",
            session_id=session_id,
            invocation_id=turn.invocation_id,
            status=status.value,
            sequence=turn.sequence,
        )
        return preserved

    async def cancel_active_turn(self, session_id: str) -> str:
        """Cancel the active turn, returning the partial prose accumulated so far.

        The turn is removed from the registry.  Returns an empty string if
        there is no active turn.
        """
        turn = self._turns.pop(session_id, None)
        if turn is None:
            return ""
        logger.info(
            "active_turn_cancelled",
            session_id=session_id,
            invocation_id=turn.invocation_id,
            sequence=turn.sequence,
        )
        return turn.partial_prose

    async def get_active_snapshot(self, session_id: str) -> ActiveTurnSnapshot | None:
        """Return an immutable snapshot of the active turn, or ``None``."""
        turn = self._turns.get(session_id)
        if turn is None:
            return None
        return self._snapshot(turn)

    async def get_active_partial(self, session_id: str) -> str:
        """Return the current partial prose, or an empty string if no active turn."""
        turn = self._turns.get(session_id)
        if turn is None:
            return ""
        return turn.partial_prose

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot(turn: _ActiveTurn) -> ActiveTurnSnapshot:
        return ActiveTurnSnapshot(
            invocation_id=turn.invocation_id,
            sequence=turn.sequence,
            partial_prose=turn.partial_prose,
        )
