"""WebSocket direction-message transport dispatch orchestration (ADR-052).

Stores the user direction and spawns the streaming turn as a decoupled
``asyncio.Task`` registered in the :class:`ActiveTurnRegistry`, then
returns immediately so the receive loop is free to accept the next
message (including ``stop_generation``).

The streaming task itself — chunk recording, cancellation, error and
completion handling, registry cleanup, the benign end_session race
(ADR-052, PR #157 follow-up) — is owned by
:mod:`narrare.writing._ws_direction_stream`; this module only
orchestrates the dispatch and attaches the done-callback safety net.

See: ADR-052, ADR-045, CONSTRAINTS.md RULE-04/RULE-06/RULE-12/RULE-20.
"""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from narrare.writing._ws_direction_stream import (
    mark_stream_status,
    on_stream_done,
    run_direction_stream,
)
from narrare.writing.ws_sink import WebSocketSink

if TYPE_CHECKING:
    from narrare.writing.ws_active_turn_registry import ActiveTurnRegistry
    from narrare.writing.ws_session_context import WritingSessionContext
    from narrare.writing.ws_streaming import StreamSender
    from narrare.writing.ws_turn_service import WritingTurnService
    from narrare_core.writing.session_manager import SessionManager
    from narrare_core.writing.session_turn_state import SessionTurnStateStore


class WritingDirectionDispatcher:
    """Dispatch ``user_direction`` messages over the WebSocket transport.

    Spawns streaming as a background task registered in the
    :class:`ActiveTurnRegistry` (ADR-052 Decision 1). The receive loop
    is never blocked by streaming.

    Args:
        session_manager: Session state manager for transcript persistence.
        turn_state: In-process store for active-turn partial prose.
        registry: Active-turn registry for cancellable task handles.
        turn_service: Transport-agnostic writing turn orchestrator.
        api_key: Optional provider API key override.
        base_url: Optional provider base URL override.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        turn_state: SessionTurnStateStore,
        registry: ActiveTurnRegistry,
        turn_service: WritingTurnService,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._turn_state = turn_state
        self._registry = registry
        self._turn_service = turn_service
        self._api_key = api_key
        self._base_url = base_url

    async def dispatch(
        self,
        websocket: StreamSender,
        context: WritingSessionContext,
        content: str,
    ) -> UUID | None:
        """Store a user direction and spawn the streaming turn.

        Returns the ``invocation_id`` on success, or ``None`` if a
        generation is already in progress (busy guard).

        Args:
            websocket: Transport with an async ``send_json`` method.
            context: Connection-scoped identifiers and session mode.
            content: User direction text.
        """
        session_id_str = str(context.session_id)

        # Busy guard — one active turn per session (ADR-052)
        if self._registry.get(session_id_str) is not None:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "A generation is already in progress. "
                    "Stop it before sending a new direction.",
                },
            )
            return None

        await self._session_manager.add_message(context.session_id, "user", content)

        invocation_id = uuid4()
        await self._turn_state.register_active_turn(
            session_id_str,
            str(invocation_id),
        )
        await mark_stream_status(self._session_manager, context.session_id, "streaming")

        sink = WebSocketSink(websocket)
        task = asyncio.ensure_future(
            run_direction_stream(
                session_manager=self._session_manager,
                turn_state=self._turn_state,
                registry=self._registry,
                turn_service=self._turn_service,
                api_key=self._api_key,
                base_url=self._base_url,
                context=context,
                content=content,
                invocation_id=invocation_id,
            ),
        )
        # Last-resort safety net for the decoupled task (PR #157 follow-up):
        # retrieves any escaped exception and guarantees registry cleanup.
        # The strong ref lives in the ActiveTurnRegistry — no GC guard set.
        task.add_done_callback(functools.partial(self._on_stream_done, session_id_str))
        self._registry.register(
            session_id_str,
            str(invocation_id),
            task=task,
            sink=sink,
        )

        return invocation_id

    def _on_stream_done(
        self,
        session_id: str,
        task: asyncio.Task[str | None],
    ) -> None:
        """Done-callback entry attached at the dispatch site (PR #157 follow-up).

        Retrieves any escaped exception and guarantees registry cleanup.
        The implementation lives in
        :func:`narrare.writing._ws_direction_stream.on_stream_done` — see
        there for the full semantics (idempotent on normal paths).
        """
        on_stream_done(self._registry, session_id, task)
