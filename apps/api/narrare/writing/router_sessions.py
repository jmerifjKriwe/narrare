"""Writing session routes — WebSocket interactive sessions.

Extracted from ``router.py`` for RULE-04 compliance (max 150 lines).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, WebSocket

from narrare._app.dependencies import get_composer, get_model_registry
from narrare._app.rate_limits import AI_WS_LIMITER

router = APIRouter(tags=["writing"])


@router.websocket("/writing/sessions/{chapter_id}")
async def interactive_session(
    websocket: WebSocket,
    chapter_id: UUID,
    user_id: str = "",
    project_id: UUID | None = None,
    mode: str = "interactive_session",
    session_id: UUID | None = None,
) -> None:
    """WebSocket endpoint for interactive writing sessions.

    Args:
        mode: Session mode — ``interactive_session`` (collaborative writing)
            or ``interview_assisted`` (structured interview → draft).
    """
    from narrare.writing.deps_ws import (
        get_active_turn_registry,
        get_session_control_service,
        get_session_manager,
        get_turn_state,
    )
    from narrare.writing.ws_factory import build_writing_session_handler

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

    # Origin validation (CSRF defense-in-depth, AUFG-05-13)
    from narrare._app.config import get_settings

    _settings = get_settings()
    _trusted = _settings.csrf_trusted_origins
    _origin = websocket.headers.get("origin", "")
    if _origin and _origin not in _trusted:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "message": "Origin not allowed",
            }
        )
        await websocket.close(code=4001, reason="Origin not allowed")
        return

    # Rate-limit check (in-memory, AR-05-02)
    ws_key = f"ws:writing:{user_id}:{chapter_id}"
    if not AI_WS_LIMITER.try_acquire(ws_key, blocking=False):
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "message": "Rate limited — too many writing sessions. Try again later.",
            }
        )
        await websocket.close(code=4003, reason="Rate limited")
        return

    session_manager = get_session_manager(websocket.app)
    active_turn_registry = get_active_turn_registry(websocket.app)
    turn_state = get_turn_state(websocket.app)
    control_service = get_session_control_service(
        websocket.app,
        session_manager=session_manager,
        registry=active_turn_registry,
        turn_state=turn_state,
    )
    model_registry = get_model_registry()
    composer = get_composer()

    # Resolve token limits from DB — replaces hardcoded defaults
    from narrare._app.config import get_settings
    from narrare._app.database import get_async_session
    from narrare._app.dependencies_pipeline import get_invocation_pipeline
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    _session_gen = get_async_session()
    session = await _session_gen.__anext__()
    try:
        token_limits_service = TokenLimitsService(
            user_repo=UserTokenLimitsRepository(session),
            project_repo=ProjectTokenLimitsRepository(session),
            config=get_settings(),
        )
        limits = await token_limits_service.get_resolved_limits(
            user_id=user_id,
            project_id=str(project_id) if project_id else None,
        )

        # Resolve model config per-user via routing resolver (RULE-18)
        from dataclasses import replace as dataclass_replace

        from narrare._app.dependencies_services import get_model_routing_resolver
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.llm.run_limits import DefaultRunLimitResolver

        resolver = get_model_routing_resolver(session)
        resolved = await resolver.resolve(
            LLMIntent.WRITE,
            UUID(user_id),
            project_id,
        )
        config = dataclass_replace(
            resolved.config,
            temperature=0.7,
            max_tokens=limits.output_limit,
        )
    finally:
        await _session_gen.aclose()
    handler = build_writing_session_handler(
        session_manager=session_manager,
        registry=active_turn_registry,
        turn_state=turn_state,
        control_service=control_service,
        model_registry=model_registry,
        composer=composer,
        config=config,
        invocation_pipeline=get_invocation_pipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
        mode=mode,
        ws_idle_timeout=limits.ws_timeout,
    )
    await handler.handle(websocket, chapter_id, user_id, project_id, session_id=session_id)
