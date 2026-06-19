"""WebSocket transport loop for interactive writing sessions.

Owns connection acceptance, session lifecycle, greeting, receive loop,
timeout/disconnect handling, and final cleanup. Message routing is delegated
to ``WritingSessionMessageRouter``; prompt/model orchestration lives in the
turn service and draft generator (ADR-045 Decision 6).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from narrare.writing.ws_session_context import WritingSessionContext

if TYPE_CHECKING:
    from narrare.writing.ws_message_router import WritingSessionMessageRouter
    from narrare_core.writing.session_manager import SessionManager

logger = structlog.get_logger(__name__)


class WritingSessionHandler:
    """Handles WebSocket connections for interactive writing sessions.

    Supports ``interactive_session`` and ``interview_assisted`` modes.
    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(
        self,
        session_manager: SessionManager,
        message_router: WritingSessionMessageRouter,
        mode: str = "interactive_session",
        ws_idle_timeout: int = 1800,
    ) -> None:
        self._session_manager = session_manager
        self._message_router = message_router
        self._mode = mode
        self._ws_idle_timeout = ws_idle_timeout

    async def handle(
        self,
        websocket: WebSocket,
        chapter_id: UUID,
        user_id: str,
        project_id: UUID,
    ) -> None:
        """Handle a WebSocket session lifecycle.

        Accepts the connection, creates a session, and enters the
        message loop.  Cleans up on disconnect or timeout.
        """
        await websocket.accept()

        session_id: UUID | None = None
        try:
            user_uuid = UUID(user_id)
            session_id = await self._session_manager.create_session(
                chapter_id=chapter_id,
                project_id=project_id,
                user_id=user_uuid,
            )
            context = WritingSessionContext(
                session_id=session_id,
                user_id=user_uuid,
                project_id=project_id,
                chapter_id=chapter_id,
                mode=self._mode,
            )

            await self._send_greeting(websocket, context)

            # Message loop with configurable idle timeout
            while True:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=self._ws_idle_timeout,
                )
                await self._message_router.route(websocket, context, data)

        except WebSocketDisconnect:
            logger.info(
                "session_disconnected",
                session_id=str(session_id),
                chapter_id=str(chapter_id),
            )
        except TimeoutError:
            await self._handle_timeout(websocket, session_id)
        except Exception as e:
            logger.error(
                "session_error",
                session_id=str(session_id),
                error=str(e),
            )
            await self._safe_send(
                websocket,
                {
                    "type": "error",
                    "message": "Internal session error",
                },
            )
        finally:
            if session_id is not None:
                await self._session_manager.end_session(session_id)

    async def _handle_timeout(
        self,
        websocket: WebSocket,
        session_id: UUID | None,
    ) -> None:
        """Handle idle timeout gracefully."""
        logger.info(
            "session_timeout",
            session_id=str(session_id),
        )
        await self._safe_send(
            websocket,
            {
                "type": "timeout",
                "message": "Session timed out due to inactivity",
            },
        )

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
