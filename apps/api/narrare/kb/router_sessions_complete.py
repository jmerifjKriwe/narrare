"""KB session complete route — extracted from router_sessions.py for RULE-04.

Creates the KB entry from session fields before marking the session
as complete. Returns both the serialized session and the entry ID.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from narrare._app.dependencies import CurrentUserIdDep
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.kb.dependencies import get_kb_session_service
from narrare.kb.session_schemas import CompleteSessionRequest, KBSessionCompleteResponse
from narrare.kb.session_service import KBSessionService

router = APIRouter(tags=["kb-sessions"])


@router.post(
    "/novels/{novel_id}/kb/sessions/{session_id}/complete",
    dependencies=[Depends(AI_ANALYSIS_LIMITER)],
)
async def complete_session(
    novel_id: UUID,
    session_id: UUID,
    user_id: CurrentUserIdDep,
    request: CompleteSessionRequest | None = None,
    service: KBSessionService = Depends(get_kb_session_service),
) -> KBSessionCompleteResponse:
    """Complete a KB creation session and create the KB entry.

    Creates a KB entry from the session's collected fields and marks
    the session as complete. Returns the updated session and the
    new entry's ID.

    The body is optional (F9-1): ``{"name": ...}`` supplies the entry
    name collected by the FE; an absent body or absent name keeps the
    existing behavior (400 when the session has no name).
    """
    try:
        session, entry_id = await service.complete_session(
            session_id, novel_id, UUID(user_id), name=request.name if request else None
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KBSessionCompleteResponse(
        session=session.model_dump(mode="json"),
        entry_id=str(entry_id),
    )
