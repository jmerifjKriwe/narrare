"""WebSocket transport loop for interactive writing sessions.

Owns connection acceptance, session lifecycle, greeting, receive loop,
timeout/disconnect handling, and final cleanup. Message routing is delegated
to ``WritingSessionMessageRouter``; prompt/model orchestration lives in the
turn service and draft generator (ADR-045 Decision 6).

ADR-052: The session is **not** ended on disconnect. The turn keeps running
(bound to the registry), the cache persists, and an idle timeout emits
``connection_lost`` so the client can recover. The session remains
recoverable until the cache TTL expires.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from narrare.writing.ws_payloads import (
    build_recovery_failed_payload,
    build_session_recovered_payload,
)
from narrare.writing.ws_session_context import WritingSessionContext
from narrare_core.writing._enums import ConnectionState

if TYPE_CHECKING:
    from collections.abc import Mapping

    from narrare.writing.contracts import WritingSessionControlProtocol
    from narrare.writing.ws_active_turn_registry import SessionTransportSink
    from narrare.writing.ws_message_router import WritingSessionMessageRouter
    from narrare_core.writing.session_manager import SessionManager

logger = structlog.get_logger(__name__)


class WritingSessionHandler:
    """Handles WebSocket connections for interactive writing sessions.

    Supports ``interactive_session`` and ``interview_assisted`` modes.
    Dependencies are injected via constructor (DI pattern).

    ADR-052: On disconnect, the session is marked ``disconnected`` (not
    ended) so a reconnect can reattach. On idle timeout, ``connection_lost``
    is emitted before marking disconnected.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        control_service: WritingSessionControlProtocol,
        message_router: WritingSessionMessageRouter,
        mode: str = "interactive_session",
        ws_idle_timeout: int = 1800,
    ) -> None:
        self._session_manager = session_manager
        self._control_service = control_service
        self._message_router = message_router
        self._mode = mode
        self._ws_idle_timeout = ws_idle_timeout

    async def handle(
        self,
        websocket: WebSocket,
        chapter_id: UUID,
        user_id: str,
        project_id: UUID,
        *,
        session_id: UUID | None = None,
    ) -> None:
        """Handle a WebSocket session lifecycle.

        If ``session_id`` is provided, attempts to reattach to an existing
        session (ADR-052 Phase 2). Otherwise creates a new session.

        On disconnect or timeout, marks the session ``disconnected``
        (does NOT end it) so a reconnect can recover.
        """
        await websocket.accept()

        active_session_id: UUID | None = None
        try:
            user_uuid = UUID(user_id)

            if session_id is not None:
                # Reattach path (ADR-052 Phase 2)
                outcome = await self._control_service.reattach_session(
                    session_id,
                    user_uuid,
                    project_id,
                    new_sink=self._make_sink(websocket),
                )
                if outcome.get("kind") == "recovered":
                    # session_id is a Required key — always present per contract.
                    active_session_id = UUID(outcome["session_id"])
                    await self._send_session_recovered(websocket, outcome)
                else:
                    await self._send_recovery_failed(websocket, outcome)
                    await websocket.close(code=4404)
                    return
            else:
                # Fresh session path
                active_session_id = await self._session_manager.create_session(
                    chapter_id=chapter_id,
                    project_id=project_id,
                    user_id=user_uuid,
                )

            context = WritingSessionContext(
                session_id=active_session_id,
                user_id=user_uuid,
                project_id=project_id,
                chapter_id=chapter_id,
                mode=self._mode,
            )

            if session_id is None:
                await self._send_greeting(websocket, context)

            # Mark connection as connected
            await self._mark_connection_state(active_session_id, ConnectionState.CONNECTED)

            # Message loop with configurable idle timeout.
            # route() returns False for end_session so we break cleanly
            # before the next receive_json() would raise a RuntimeError
            # on a closed WebSocket.
            while True:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=self._ws_idle_timeout,
                )
                should_continue = await self._message_router.route(websocket, context, data)
                if not should_continue:
                    break

        except WebSocketDisconnect:
            logger.info(
                "session_disconnected",
                session_id=str(active_session_id),
                chapter_id=str(chapter_id),
            )
            await self._mark_disconnected(active_session_id)
        except TimeoutError:
            await self._handle_timeout(websocket, active_session_id)
        except Exception as e:
            logger.error(
                "session_error",
                session_id=str(active_session_id),
                error=str(e),
            )
            await self._safe_send(
                websocket,
                {
                    "type": "error",
                    "message": "Internal session error",
                },
            )
        # ADR-052: No end_session in finally — session stays recoverable.

    async def _handle_timeout(
        self,
        websocket: WebSocket,
        session_id: UUID | None,
    ) -> None:
        """Handle idle timeout — emit connection_lost and mark disconnected."""
        logger.info(
            "session_timeout",
            session_id=str(session_id),
        )
        await self._safe_send(
            websocket,
            {
                "type": "connection_lost",
                "message": "Connection lost due to inactivity",
            },
        )
        await self._mark_disconnected(session_id)

    @staticmethod
    async def _send_greeting(
        websocket: WebSocket,
        context: WritingSessionContext,
    ) -> None:
        """Send the mode-aware initial greeting."""
        if context.mode == "interview_assisted":
            await websocket.send_json(
                {
                    "type": "greeting",
                    "mode": "interview",
                    "session_id": str(context.session_id),
                }
            )
            return
        await websocket.send_json(
            {
                "type": "greeting",
                "message": "What would you like to write today?",
                "session_id": str(context.session_id),
            }
        )

    @staticmethod
    async def _send_session_recovered(
        websocket: WebSocket,
        outcome: Mapping[str, object],
    ) -> None:
        """Send the session_recovered message with snapshot fields."""
        await websocket.send_json(
            build_session_recovered_payload(outcome),
        )

    @staticmethod
    async def _send_recovery_failed(
        websocket: WebSocket,
        outcome: Mapping[str, object],
    ) -> None:
        """Send the recovery_failed message with the typed reason."""
        await websocket.send_json(
            build_recovery_failed_payload(outcome),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _mark_connection_state(
        self,
        session_id: UUID,
        state: ConnectionState,
    ) -> None:
        """Best-effort update of ``connection_state`` on the cached state."""
        try:
            session_state = await self._session_manager._load(session_id)  # pyright: ignore[reportPrivateUsage]
            if session_state is not None:
                session_state.connection_state = state
                await self._session_manager._persist(session_state)  # pyright: ignore[reportPrivateUsage]
        except Exception:
            logger.debug(
                "connection_state_update_failed",
                session_id=str(session_id),
                state=state.value,
            )

    async def _mark_disconnected(self, session_id: UUID | None) -> None:
        """Mark the session as disconnected (ADR-052 — no auto-end)."""
        if session_id is None:
            return
        await self._mark_connection_state(session_id, ConnectionState.DISCONNECTED)

    @staticmethod
    async def _safe_send(
        websocket: WebSocket,
        data: dict[str, object],
    ) -> None:
        """Send JSON without raising on disconnect."""
        try:
            await websocket.send_json(data)
        except Exception:
            logger.debug("ws_send_failed", hint="client likely disconnected")

    @staticmethod
    def _make_sink(websocket: WebSocket) -> SessionTransportSink:
        """Build a transport sink for reattach without widening handler imports."""
        from narrare.writing.ws_sink import WebSocketSink

        return WebSocketSink(websocket)
