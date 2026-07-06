"""Writing session control service (ADR-052).

Implements :class:`WritingSessionControlProtocol` — the service-layer
control surface for server-side stop and WebSocket recovery.

Owns the coordination between the :class:`ActiveTurnRegistry`
(task cancellation), :class:`SessionTurnStateStore` (partial prose),
and :class:`SessionManager` (session validation / reattach).

See: docs/architecture/decisions/ADR-052-session-stop-recovery.md
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing.contracts import (
    ReattachOutcomeKind,
    ReattachSessionResult,
    StopGenerationResult,
    StopGenerationStatus,
    WritingSessionControlProtocol,
)
from narrare_core.writing._enums import ConnectionState, StreamStatus
from narrare_core.writing.requests import (
    Reattached,
    ReattachOutcome,
    SessionExpired,
    SessionNotFound,
)

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.writing.ws_active_turn_registry import (
        ActiveTurnRegistry,
        SessionTransportSink,
    )
    from narrare_core.writing.session_manager import SessionManager
    from narrare_core.writing.session_turn_state import SessionTurnStateStore

logger = structlog.get_logger(__name__)

__all__ = ["WritingSessionControlService"]


class WritingSessionControlService(WritingSessionControlProtocol):
    """Stop generation and reattach sessions for WebSocket writing (ADR-052).

    Args:
        session_manager: Session state manager for validation and reattach.
        turn_state: In-process store of active-turn partial prose.
        registry: Active-turn registry holding live ``asyncio.Task`` handles.
    """

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        turn_state: SessionTurnStateStore,
        registry: ActiveTurnRegistry,
    ) -> None:
        self._session_manager = session_manager
        self._turn_state = turn_state
        self._registry = registry

    # ------------------------------------------------------------------
    # stop_generation
    # ------------------------------------------------------------------

    async def stop_generation(
        self,
        session_id: UUID,
        invocation_id: UUID,
    ) -> StopGenerationResult:
        """Cancel the active streaming turn for ``session_id``.

        1. Read partial prose from :class:`SessionTurnStateStore`.
        2. Cancel the ``asyncio.Task`` via :class:`ActiveTurnRegistry`.
        3. Return the typed result dict.

        Returns ``status=stopped`` with the partial prose if a turn was
        cancelled; ``status=no_active_turn`` otherwise.
        """
        session_id_str = str(session_id)
        snapshot = await self._turn_state.get_active_snapshot(session_id_str)
        sequence = snapshot.sequence if snapshot is not None else 0
        partial = await self._turn_state.cancel_active_turn(session_id_str)
        result = self._registry.cancel(str(session_id), partial_prose=partial)

        if result.cancelled:
            logger.info(
                "stop_generation_cancelled",
                session_id=str(session_id),
                invocation_id=str(invocation_id),
                partial_len=len(partial),
            )
            return {
                "status": StopGenerationStatus.STOPPED,
                "partial_prose": partial,
                "invocation_id": str(invocation_id),
                "sequence": sequence,
            }

        logger.info(
            "stop_generation_no_active_turn",
            session_id=str(session_id),
            invocation_id=str(invocation_id),
        )
        return {
            "status": StopGenerationStatus.NO_ACTIVE_TURN,
            "partial_prose": "",
            "invocation_id": str(invocation_id),
            "sequence": 0,
        }

    # ------------------------------------------------------------------
    # reattach_session
    # ------------------------------------------------------------------

    async def reattach_session(
        self,
        session_id: UUID,
        user_id: UUID,
        project_id: UUID,
        *,
        new_sink: SessionTransportSink | None = None,
    ) -> ReattachSessionResult:
        """Reattach to an existing session after a transport reconnect.

        Delegates to
        :meth:`SessionManager.reattach_session` for ownership/expiry
        validation, then converts the typed
        :class:`ReattachOutcome` to a serializable dict.
        """
        outcome = await self._session_manager.reattach_session(
            session_id,
            user_id,
            project_id,
        )
        result = self._outcome_to_dict(outcome)
        if isinstance(outcome, Reattached):
            result["transcript_tail"] = await self._load_transcript_tail(outcome.session_id)
            await self._reconcile_successful_reattach(outcome, result, new_sink)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _outcome_to_dict(outcome: ReattachOutcome) -> ReattachSessionResult:
        """Convert a :class:`ReattachOutcome` to a serializable dict.

        Uses ``isinstance`` to pattern-match on the discriminated union
        and serializes ``outcome.kind`` into the dict payload.
        """
        if isinstance(outcome, Reattached):
            return {
                "kind": ReattachOutcomeKind.RECOVERED,
                "session_id": str(outcome.session_id),
                "stream_status": outcome.stream_status.value,
                "last_sequence": outcome.last_sequence,
                "active_partial_prose": outcome.active_partial_prose,
                "active_invocation_id": (
                    str(outcome.active_invocation_id)
                    if outcome.active_invocation_id is not None
                    else None
                ),
            }
        if isinstance(outcome, SessionNotFound):
            return {
                "kind": ReattachOutcomeKind.NOT_FOUND,
                "session_id": str(outcome.session_id),
            }
        if isinstance(outcome, SessionExpired):
            return {
                "kind": ReattachOutcomeKind.EXPIRED,
                "session_id": str(outcome.session_id),
            }
        # Remaining variant is OwnershipMismatch (ReattachOutcome is a closed union)
        return {
            "kind": ReattachOutcomeKind.OWNERSHIP_MISMATCH,
            "session_id": str(outcome.session_id),
        }

    async def _reconcile_successful_reattach(
        self,
        outcome: Reattached,
        result: ReattachSessionResult,
        new_sink: SessionTransportSink | None,
    ) -> None:
        """Rebind a live turn and reconcile stale streaming state.

        ``SessionManager.reattach_session`` deliberately does not mutate
        connection state. The backend control service owns those transport
        transitions (ADR-052 Phase 2).
        """
        session_id_str = str(outcome.session_id)
        live_turn = self._registry.get(session_id_str)
        if live_turn is not None:
            if new_sink is not None:
                self._registry.rebind_sink(session_id_str, new_sink)
            snapshot = await self._turn_state.get_active_snapshot(session_id_str)
            if snapshot is not None:
                result["active_invocation_id"] = snapshot.invocation_id
                result["active_partial_prose"] = snapshot.partial_prose
                result["last_sequence"] = snapshot.sequence
                await self._persist_recovery_fields(
                    outcome.session_id,
                    stream_status=StreamStatus.STREAMING,
                    active_invocation_id=outcome.active_invocation_id,
                    active_partial_prose=snapshot.partial_prose,
                    last_sequence=snapshot.sequence,
                    connection_state=ConnectionState.CONNECTED,
                )
            else:
                await self._persist_recovery_fields(
                    outcome.session_id,
                    connection_state=ConnectionState.CONNECTED,
                )
            logger.info("session_reattached_live_turn", session_id=session_id_str)
            return

        if outcome.stream_status is StreamStatus.STREAMING:
            # Lazy cold-start reconciliation: cache said streaming, but this
            # process has no live Task handle. Mark stopped honestly rather
            # than pretending the server can recover a non-existent task.
            result["stream_status"] = StreamStatus.STOPPED.value
            await self._persist_recovery_fields(
                outcome.session_id,
                stream_status=StreamStatus.STOPPED,
                connection_state=ConnectionState.CONNECTED,
            )
            logger.info("session_reattach_reconciled_stale_stream", session_id=session_id_str)
            return

        await self._persist_recovery_fields(
            outcome.session_id,
            connection_state=ConnectionState.CONNECTED,
        )

    async def _load_transcript_tail(self, session_id: UUID) -> list[dict[str, str]]:
        """Load the recoverable transcript tail from cached session state."""
        state = await self._session_manager._load(session_id)  # pyright: ignore[reportPrivateUsage]
        if state is None:
            return []
        return [dict(item) for item in state.conversation_history]

    async def _persist_recovery_fields(
        self,
        session_id: UUID,
        *,
        stream_status: StreamStatus | None = None,
        active_invocation_id: UUID | None = None,
        active_partial_prose: str | None = None,
        last_sequence: int | None = None,
        connection_state: ConnectionState | None = None,
    ) -> None:
        """Best-effort persistence of backend-owned recovery fields."""
        try:
            state = await self._session_manager._load(session_id)  # pyright: ignore[reportPrivateUsage]
            if state is None:
                return
            if stream_status is not None:
                state.stream_status = stream_status
            if active_invocation_id is not None:
                state.active_invocation_id = active_invocation_id
            if active_partial_prose is not None:
                state.active_partial_prose = active_partial_prose
            if last_sequence is not None:
                state.last_sequence = last_sequence
            if connection_state is not None:
                state.connection_state = connection_state
            await self._session_manager._persist(state)  # pyright: ignore[reportPrivateUsage]
        except Exception:
            logger.debug(
                "reattach_recovery_field_persist_failed",
                session_id=str(session_id),
                exc_info=True,
            )
