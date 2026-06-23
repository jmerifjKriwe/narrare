"""Writing-session control contracts (ADR-052).

Split from ``contracts.py`` for RULE-04: the stop/recovery WebSocket control
surface is one focused contract group and is re-exported by ``contracts.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, Required, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.writing.ws_active_turn_registry import SessionTransportSink


class StopGenerationStatus:
    """Status vocabulary for stop-generation results."""

    STOPPED = "stopped"
    NO_ACTIVE_TURN = "no_active_turn"


class ReattachOutcomeKind:
    """Outcome vocabulary for session reattach results."""

    RECOVERED = "recovered"
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    OWNERSHIP_MISMATCH = "ownership_mismatch"


type StopGenerationStatusValue = Literal["stopped", "no_active_turn"]
type ReattachOutcomeKindValue = Literal[
    "recovered",
    "not_found",
    "expired",
    "ownership_mismatch",
]


class StopGenerationResult(TypedDict):
    """Internal service DTO for ADR-052 stop-generation results."""

    status: StopGenerationStatusValue
    partial_prose: str
    invocation_id: str
    sequence: int


class ReattachSessionResult(TypedDict, total=False):
    """Internal service DTO for ADR-052 reattach outcomes.

    ``kind`` and ``session_id`` are always present in every outcome variant
    (see :meth:`WritingSessionControlService._outcome_to_dict`); the snapshot
    fields below are populated only for the ``recovered`` outcome.
    """

    kind: Required[ReattachOutcomeKindValue]
    session_id: Required[str]
    stream_status: str
    last_sequence: int
    active_partial_prose: str
    active_invocation_id: str | None
    transcript_tail: list[dict[str, str]]


@runtime_checkable
class WritingSessionControlProtocol(Protocol):
    """Service-layer control surface for writing sessions (ADR-052).

    Owns server-side stop and reattach operations that coordinate the active
    turn registry, turn-state store, and session manager.
    """

    async def stop_generation(
        self,
        session_id: UUID,
        invocation_id: UUID,
    ) -> StopGenerationResult:
        """Cancel the active streaming turn for ``session_id``.

        Returns an internal DTO with ``status``, ``partial_prose``,
        ``invocation_id``, and ``sequence`` keys.
        """
        ...

    async def reattach_session(
        self,
        session_id: UUID,
        user_id: UUID,
        project_id: UUID,
        *,
        new_sink: SessionTransportSink | None = None,
    ) -> ReattachSessionResult:
        """Reattach to an existing session after a transport reconnect.

        Returns a dict with a ``kind`` discriminator. On ``recovered``, the
        payload includes the session snapshot fields used by WebSocket clients.
        """
        ...
