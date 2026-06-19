"""WebSocket direction-message transport dispatcher.

Handles the transport-specific work for one ``user_direction`` message:
store the user message, stream turn-service chunks through the WebSocket DTO
adapter, persist the assistant response, and emit the completion DTO.

The prompt/model-call orchestration remains in ``WritingTurnService``; stream
DTO conversion remains in ``ws_streaming``. This module is the glue between
those transport-agnostic services and WebSocket session state.

See: ADR-045, CONSTRAINTS.md RULE-04/RULE-06/RULE-12/RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing.ws_streaming import send_stream_chunks
from narrare_core.shared.errors import WritingError

if TYPE_CHECKING:
    from narrare.writing.ws_session_context import WritingSessionContext
    from narrare.writing.ws_streaming import StreamSender
    from narrare.writing.ws_turn_service import WritingTurnService
    from narrare_core.writing.session_manager import SessionManager

logger = structlog.get_logger(__name__)


class WritingDirectionDispatcher:
    """Dispatch ``user_direction`` messages over the WebSocket transport.

    Args:
        session_manager: Session state manager for transcript persistence.
        turn_service: Transport-agnostic writing turn orchestrator.
        api_key: Optional provider API key override.
        base_url: Optional provider base URL override.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        turn_service: WritingTurnService,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._turn_service = turn_service
        self._api_key = api_key
        self._base_url = base_url

    async def dispatch(
        self,
        websocket: StreamSender,
        context: WritingSessionContext,
        content: str,
    ) -> None:
        """Store a user direction and stream the generated response.

        Args:
            websocket: Transport with an async ``send_json`` method.
            context: Connection-scoped identifiers and session mode.
            content: User direction text.
        """
        await self._session_manager.add_message(context.session_id, "user", content)

        try:
            result = await send_stream_chunks(
                websocket,
                self._turn_service.stream_turn(
                    content=content,
                    session_mode=context.mode,
                    user_id=context.user_id,
                    project_id=context.project_id,
                    chapter_id=context.chapter_id,
                    session_id=context.session_id,
                    api_key=self._api_key,
                    base_url=self._base_url,
                ),
            )
        except WritingError as e:
            logger.error(
                "direction_generation_failed",
                session_id=str(context.session_id),
                error=str(e),
            )
            await websocket.send_json({"type": "error", "message": str(e)})
            return
        except Exception as e:
            logger.error(
                "direction_generation_failed",
                session_id=str(context.session_id),
                error=str(e),
            )
            await websocket.send_json({"type": "error", "message": f"Generation failed: {e}"})
            return

        if not result.full_text:
            return

        await self._session_manager.add_message(
            context.session_id,
            "assistant",
            result.full_text,
        )
        message: dict[str, object] = {"type": "text_done", "text": result.full_text}
        if result.usage is not None:
            message["usage"] = {
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
                "total_tokens": result.usage.total_tokens,
            }
        await websocket.send_json(message)
