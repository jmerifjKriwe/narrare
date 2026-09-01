"""Writing session routes — WebSocket interactive sessions.

Extracted from ``router.py`` for RULE-04 compliance (max 150 lines).
Identity is server-derived (ADR-084): the handshake consumes a single-use
ticket from ``POST /api/v1/auth/ws-ticket`` — the client-asserted
``user_id`` query param is removed (sanctioned backward break).
Handshake order: ticket → ``project_id`` → origin → rate limit →
ownership gate + runtime resolution (IDOR S3, ``ws_session_config``).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, WebSocket

from narrare._app.dependencies import get_composer, get_model_registry
from narrare._app.rate_limits import AI_WS_LIMITER
from narrare_core.shared.errors import NotFoundError

router = APIRouter(tags=["writing"])


async def _close_with_error(websocket: WebSocket, *, code: int, reason: str) -> None:
    """Accept → error JSON frame → close (house pattern — browsers cannot read close codes)."""
    await websocket.accept()
    await websocket.send_json({"type": "error", "message": reason})
    await websocket.close(code=code, reason=reason)


@router.websocket("/writing/sessions/{chapter_id}")
async def interactive_session(
    websocket: WebSocket,
    chapter_id: UUID,
    token: str = "",
    project_id: UUID | None = None,
    mode: str = "interactive_session",
    session_id: UUID | None = None,
) -> None:
    """WebSocket endpoint for interactive writing sessions.

    Handshake (ADR-084): ticket → ``project_id`` → origin → rate limit; the
    ``token`` is a single-use 60 s ticket (fresh per reconnect).
    Args:
        mode: ``interactive_session`` or ``interview_assisted``.
    """
    from narrare.auth import ws_tickets
    from narrare.writing.deps_ws import (
        get_active_turn_registry,
        get_session_control_service,
        get_session_manager,
        get_turn_state,
    )
    from narrare.writing.ws_factory import build_writing_session_handler

    # 1. Ticket validation (authn, ADR-084) — identity is DERIVED from the
    #    registry record; the uniform WsTicketError message (anti-enumeration)
    #    is the client-facing reason.
    try:
        user_id = str(ws_tickets.consume(token))
    except ws_tickets.WsTicketError as exc:
        await _close_with_error(websocket, code=4401, reason=str(exc))
        return

    # 2. project_id presence
    if project_id is None:
        await _close_with_error(websocket, code=4001, reason="Missing project_id")
        return

    # 3. Origin validation (CSRF defense-in-depth, AUFG-05-13) — a policy
    #    violation per RFC 6455 §7.4.1, hence 1008 (ADR-084 reclassification).
    from narrare._app.config import get_settings

    _trusted = get_settings().csrf_trusted_origins
    _origin = websocket.headers.get("origin", "")
    if _origin and _origin not in _trusted:
        await _close_with_error(websocket, code=1008, reason="Origin not allowed")
        return

    # 4. Rate-limit check keyed on the DERIVED user (AR-05-02; unspoofable).
    ws_key = f"ws:writing:{user_id}:{chapter_id}"
    if not AI_WS_LIMITER.try_acquire(ws_key, blocking=False):
        await _close_with_error(websocket, code=4003, reason="Rate limited")
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

    # 5. Ownership gate + runtime resolution (IDOR remediation S3): the
    #    ticket-derived identity must own the project AND the chapter must
    #    belong to it — BEFORE any project-keyed settings/routing read
    #    (foreign project → transient settings row; unknown → FK
    #    IntegrityError 500-oracle). ``NotFoundError`` → close 4001;
    #    foreign ≡ unknown by construction (anti-enumeration).
    from narrare._app.dependencies_pipeline import get_invocation_pipeline
    from narrare.writing.ws_session_config import resolve_ws_session_config
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    try:
        config, limits = await resolve_ws_session_config(user_id, chapter_id, project_id)
    except NotFoundError as exc:
        await _close_with_error(websocket, code=4001, reason=str(exc))
        return

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
