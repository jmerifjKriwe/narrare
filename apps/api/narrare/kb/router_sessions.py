"""KB session routes — thin delegation to KBSessionService (RULE-06).

REST endpoints for the assisted creation session lifecycle.
Every handler delegates immediately to the service.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.kb.dependencies import get_kb_session_service
from narrare.kb.session_models import KBCreationSession
from narrare.kb.session_schemas import AnswerFieldRequest, CreateSessionRequest
from narrare.kb.session_service import KBSessionService

router = APIRouter(tags=["kb-sessions"])


def _session_to_response(session: KBCreationSession) -> dict[str, object]:
    """Convert session model to response dict."""
    return session.model_dump(mode="json")


@router.post("/novels/{novel_id}/kb/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    novel_id: UUID,
    request: CreateSessionRequest,
    user_id: CurrentUserIdDep,
    service: KBSessionService = Depends(get_kb_session_service),
) -> dict[str, object]:
    """Create a new KB creation session."""
    session = await service.create_session(
        novel_id=novel_id,
        user_id=UUID(user_id),
        entity_type=request.entity_type,
    )
    return _session_to_response(session)


@router.get("/novels/{novel_id}/kb/sessions/{session_id}")
async def get_session(
    novel_id: UUID,
    session_id: UUID,
    user_id: CurrentUserIdDep,
    service: KBSessionService = Depends(get_kb_session_service),
) -> dict[str, object]:
    """Get a KB creation session by ID."""
    session = await service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.patch("/novels/{novel_id}/kb/sessions/{session_id}/fields/{field_key}")
async def answer_field(
    novel_id: UUID,
    session_id: UUID,
    field_key: str,
    request: AnswerFieldRequest,
    user_id: CurrentUserIdDep,
    service: KBSessionService = Depends(get_kb_session_service),
) -> dict[str, object]:
    """Update a field with a user-provided value."""
    try:
        session = await service.answer_field(session_id, field_key, request.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _session_to_response(session)


@router.post(
    "/novels/{novel_id}/kb/sessions/{session_id}/suggest/{field_key}",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def request_suggestion(
    novel_id: UUID,
    session_id: UUID,
    field_key: str,
    user_id: CurrentUserIdDep,
    service: KBSessionService = Depends(get_kb_session_service),
) -> dict[str, object]:
    """Request AI suggestion for a specific field."""
    try:
        session, suggestion = await service.request_suggestion(session_id, field_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"session": _session_to_response(session), "suggestion": suggestion}


@router.post(
    "/novels/{novel_id}/kb/sessions/{session_id}/interview",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def request_interview_question(
    novel_id: UUID,
    session_id: UUID,
    user_id: CurrentUserIdDep,
    service: KBSessionService = Depends(get_kb_session_service),
) -> dict[str, object]:
    """Get next interview question from AI."""
    try:
        session, question = await service.request_interview_question(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"session": _session_to_response(session), "question": question}


@router.post(
    "/novels/{novel_id}/kb/sessions/{session_id}/enhance",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def request_enhancement(
    novel_id: UUID,
    session_id: UUID,
    user_id: CurrentUserIdDep,
    service: KBSessionService = Depends(get_kb_session_service),
) -> dict[str, object]:
    """Request AI enhancement of the entire entry."""
    try:
        session, enhancement = await service.request_enhancement(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"session": _session_to_response(session), "enhancement": enhancement}


@router.delete(
    "/novels/{novel_id}/kb/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def abandon_session(
    novel_id: UUID,
    session_id: UUID,
    user_id: CurrentUserIdDep,
    service: KBSessionService = Depends(get_kb_session_service),
) -> None:
    """Abandon and delete a session."""
    try:
        await service.abandon_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
