"""WebSocket handler for interactive writing sessions.

Handles the full lifecycle of a WebSocket-based writing session:
connection acceptance, message routing, LLM interaction, and cleanup.

Delegates to:
- :class:`SessionManager` for session state
- :class:`WritingPipeline` for generation
- :class:`LLMGateway` for LLM calls (RULE-01)
- :class:`PromptComposer` for prompt assembly (RULE-02)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from fastapi import WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from narrare_core.llm.gateway import LLMGateway
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.pipeline import WritingPipeline
    from narrare_core.writing.session_manager import SessionManager

logger = structlog.get_logger(__name__)


class WritingSessionHandler:
    """Handles WebSocket connections for interactive writing sessions.

    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(
        self,
        session_manager: SessionManager,
        pipeline: WritingPipeline,
        gateway: LLMGateway,
        composer: PromptComposer,
        config: ResolvedModelConfig,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._pipeline = pipeline
        self._gateway = gateway
        self._composer = composer
        self._config = config
        self._api_key = api_key
        self._base_url = base_url

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
            session_id = await self._session_manager.create_session(
                chapter_id=chapter_id,
                project_id=project_id,
                user_id=UUID(user_id),
            )

            await websocket.send_json(
                {
                    "type": "greeting",
                    "message": "What would you like to write today?",
                    "session_id": str(session_id),
                }
            )

            # Message loop with 30-minute idle timeout
            while True:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30 * 60,
                )
                await self._route_message(websocket, session_id, data)

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

    # ------------------------------------------------------------------
    # Message routing
    # ------------------------------------------------------------------

    async def _route_message(
        self,
        websocket: WebSocket,
        session_id: UUID,
        data: dict[str, object],
    ) -> None:
        """Route incoming WebSocket messages to handlers."""
        msg_type = data.get("type")

        if msg_type == "user_direction":
            content = data.get("content", "")
            if isinstance(content, str) and content.strip():
                await self._handle_direction(websocket, session_id, content)
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Empty direction provided",
                    }
                )
        elif msg_type == "user_feedback":
            await self._handle_feedback(websocket, session_id, data)
        elif msg_type == "save_to_chapter":
            await self._handle_save(websocket, session_id)
        elif msg_type == "end_session":
            await websocket.close()
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                }
            )

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    async def _handle_direction(
        self,
        websocket: WebSocket,
        session_id: UUID,
        content: str,
    ) -> None:
        """Handle user direction — generate text and stream back."""
        await self._session_manager.add_message(session_id, "user", content)

        # Stream generated response
        accumulated: list[str] = []
        try:
            from narrare_core.llm.intents import LLMIntent
            from narrare_core.prompts.context import PromptContext

            ctx = PromptContext(
                language="en",
                mode="interactive",
                author_instructions=content,
            )
            prompt = await self._composer.build(LLMIntent.WRITE, ctx)

            async for chunk in self._gateway.stream(
                intent=LLMIntent.WRITE,
                system_prompt=prompt.system,
                user_prompt=prompt.user,
                config=self._config,
                api_key=self._api_key,
                base_url=self._base_url,
            ):
                if chunk.is_final:
                    break
                accumulated.append(chunk.text)
                await websocket.send_json(
                    {
                        "type": "text_chunk",
                        "text": chunk.text,
                    }
                )

        except Exception as e:
            logger.error(
                "direction_generation_failed",
                session_id=str(session_id),
                error=str(e),
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Generation failed: {e}",
                }
            )
            return

        full_text = "".join(accumulated)
        if full_text:
            await self._session_manager.add_message(
                session_id,
                "assistant",
                full_text,
            )
            await websocket.send_json({"type": "text_done", "text": full_text})

    async def _handle_feedback(
        self,
        websocket: WebSocket,
        session_id: UUID,
        data: dict[str, object],
    ) -> None:
        """Handle user feedback on generated text."""
        action = data.get("action", "")
        text = data.get("text", "")

        if action == "accept" and isinstance(text, str) and text.strip():
            await self._session_manager.append_prose(session_id, text)
            await websocket.send_json(
                {
                    "type": "feedback_acknowledged",
                    "action": "accept",
                }
            )
        elif action == "reject":
            await websocket.send_json(
                {
                    "type": "feedback_acknowledged",
                    "action": "reject",
                }
            )
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Invalid feedback action: {action}",
                }
            )

    async def _handle_save(
        self,
        websocket: WebSocket,
        session_id: UUID,
    ) -> None:
        """Save prose buffer to chapter."""
        try:
            content = await self._session_manager.save_to_chapter(session_id)
            await websocket.send_json(
                {
                    "type": "saved",
                    "content": content,
                    "word_count": len(content.split()),
                }
            )
        except ValueError as e:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(e),
                }
            )

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
