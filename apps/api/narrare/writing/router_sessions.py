"""Writing session routes — WebSocket interactive sessions.

Extracted from ``router.py`` for RULE-04 compliance (max 150 lines).
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic ForwardRef resolution

from fastapi import APIRouter, WebSocket

from narrare._app.config import get_settings
from narrare._app.dependencies import get_composer, get_model_registry

# Balanced for interactive writing sessions — user can control the output
# limit via token_limit_profile once ModelRoutingResolver is available
# in the WS handler (future enhancement).
_WRITE_SESSION_DEFAULT_OUTPUT_LIMIT: int = 2000

router = APIRouter(tags=["writing"])


@router.websocket("/writing/sessions/{chapter_id}")
async def interactive_session(
    websocket: WebSocket,
    chapter_id: UUID,
    user_id: str = "",
    project_id: UUID | None = None,
    mode: str = "interactive_session",
) -> None:
    """WebSocket endpoint for interactive writing sessions.

    Args:
        mode: Session mode — ``interactive_session`` (collaborative writing)
            or ``interview_assisted`` (structured interview → draft).
    """
    from narrare.writing._ws_cache import InMemorySessionCache
    from narrare.writing.ws_handler import WritingSessionHandler
    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline
    from narrare_core.writing.session_manager import SessionManager

    if not user_id or project_id is None:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "message": "Missing user_id or project_id — please reload the page.",
            }
        )
        await websocket.close(code=4001, reason="Missing user_id or project_id")
        return

    cache = InMemorySessionCache()
    session_manager = SessionManager(cache=cache)
    registry = get_model_registry()
    composer = get_composer()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.7,
        max_tokens=_WRITE_SESSION_DEFAULT_OUTPUT_LIMIT,
    )
    assembler = WritingContextAssembler()
    draft_processor = DraftProcessor()
    pipeline = WritingPipeline(
        registry=registry,
        composer=composer,
        context_assembler=assembler,
        draft_processor=draft_processor,
    )

    settings = get_settings()
    handler = WritingSessionHandler(
        session_manager=session_manager,
        pipeline=pipeline,
        registry=registry,
        composer=composer,
        config=config,
        mode=mode,
        ws_idle_timeout=settings.ws_idle_timeout_seconds,
    )
    await handler.handle(websocket, chapter_id, user_id, project_id)
