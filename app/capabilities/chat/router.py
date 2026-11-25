"""HTTP surface. Parses, delegates to the service, streams; no logic here."""

import json
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.chat.interviews import (
    InterviewRefusalError,
    InterviewService,
)
from app.capabilities.chat.schemas import (
    ChatRequest,
    EmbeddingMismatchRead,
    SessionCreate,
    SessionDetail,
    SessionList,
    SessionRead,
    SessionSummary,
    TurnCreate,
    TurnReadback,
)
from app.capabilities.chat.service import ChatService
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from app.kernel.errors import coded_detail
from app.kernel.llm.audit import audited_stream
from app.kernel.llm.contract import CompletionRequest, Delta
from app.kernel.llm.resolution import ResolvedProvider, resolve_provider
from app.kernel.llm.streaming import (
    DONE_FRAME,
    FinalizingStreamingResponse,
    error_events,
    failure_frame,
)
from app.kernel.prompts import PromptRenderError
from app.kernel.retrieval import EmbeddingMismatchError, Passage
from app.kernel.secrets import KeyUnavailableError

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = getLogger("narrare")

SSE_HEADERS = {"Cache-Control": "no-cache"}

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]
EmbeddingsDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


def _service(session: SessionDep, user_id: UserDep, embeddings: EmbeddingsDep) -> ChatService:
    """Build the chat service with the request session, owner, and embeddings."""
    return ChatService(session, user_id, embeddings)


ServiceDep = Annotated[ChatService, Depends(_service)]


def _interview_service(session: SessionDep, user_id: UserDep) -> InterviewService:
    """Build the interview service with the request session and its owner."""
    return InterviewService(session, user_id)


InterviewServiceDep = Annotated[InterviewService, Depends(_interview_service)]


def _refusal(error: InterviewRefusalError) -> HTTPException:
    """The coded refusal: a code the surfaces localize and its sentence."""
    return HTTPException(status_code=error.status, detail=coded_detail(error.code, str(error)))


async def _events(
    resolved: ResolvedProvider, prompt: str, passages: list[Passage], user_id: UUID
) -> AsyncGenerator[str]:
    """Sources first, then the answer, then done.

    The sources go out before the first token so the reader can show what the
    answer was built from while it is still arriving. A provider that dies
    mid-stream ends with an error frame instead of done: the reader cannot see
    a traceback, and a silent close would look like a finished answer. However
    the stream ends once the provider call has started — done, error,
    disconnect, cancel — the call is audited (§3.4); a disconnect before it
    leaves no row, because no call ran.
    """
    sources = [
        {
            "chunk_id": str(passage.chunk_id),
            "document_title": passage.document_title,
            "text": passage.text,
        }
        for passage in passages
    ]
    yield f"data: {json.dumps({'sources': sources})}\n\n"
    events = audited_stream(
        resolved, CompletionRequest.user(prompt), user_id=user_id, task_key="chat.ask"
    )
    try:
        async for event in events:
            if isinstance(event, Delta):
                yield f"data: {json.dumps({'delta': event.text})}\n\n"
    except Exception as failure:
        logger.exception("chat stream failed")
        # The coded frame — what the surfaces translate: the failure's wire
        # code, the model a missing one names, the detail behind the reader's
        # disclosure. One spelling for both routers.
        yield failure_frame(failure)
    else:
        yield DONE_FRAME
    finally:
        # The inner finalizer must run deterministically: relying on the loop's
        # async-generator finalizer would lose the audit row on a disconnect.
        await events.aclose()


@router.post(
    "/ask",
    response_class=FinalizingStreamingResponse,
    status_code=200,
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "description": (
                        "Server-sent events: data frames for the sources and the answer,"
                        " then one terminal event: done or error."
                    ),
                }
            }
        },
        409: {"model": EmbeddingMismatchRead, "description": "Incompatible source embeddings"},
    },
)
async def ask(
    payload: ChatRequest, service: ServiceDep, user_id: UserDep
) -> FinalizingStreamingResponse:
    """Stream a sourced answer; return HTTP 409 for incompatible source embeddings."""
    try:
        prompt, passages = await service.prepare(payload.question, payload.limit)
    except EmbeddingMismatchError as error:
        # A dict, not a sentence: the UI localizes this error and needs a code.
        raise HTTPException(
            status_code=409,
            detail={"code": "embedding-mismatch", "stored": error.stored, "found": error.found},
        ) from None
    except PromptRenderError:
        # A prompt the effective chain refuses (an override that cannot render)
        # ends the stream the way the lost key below does: the one coded error
        # frame, refused by name and never swapped for the bundled template.
        logger.exception("chat prompt refused")
        return FinalizingStreamingResponse(
            error_events("prompt-refused"), media_type="text/event-stream", headers=SSE_HEADERS
        )
    # Resolution reads the user's profiles on the request's own session, so it
    # must run before the connection goes back. A profile whose key its tier
    # can no longer produce ends the stream with the coded error frame a dead
    # provider gets — no call ran, so no audit row.
    try:
        resolved = await resolve_provider(service.session, user_id, "chat.ask")
    except KeyUnavailableError:
        logger.exception("chat provider resolution failed")
        return FinalizingStreamingResponse(
            error_events("key-unavailable"), media_type="text/event-stream", headers=SSE_HEADERS
        )
    # The pooled connection goes back before the provider stream holds the
    # response open: nothing reads the database during the stream.
    await service.session.close()
    return FinalizingStreamingResponse(
        _events(resolved, prompt, passages, user_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/sessions", status_code=201, response_model=SessionRead)
async def open_session(payload: SessionCreate, service: InterviewServiceDep) -> SessionRead:
    """Open an interview: mode, type, novel and any target decide; a coded 404 or 422."""
    try:
        session = await service.open_session(payload)
    except InterviewRefusalError as error:
        raise _refusal(error) from None
    return SessionRead.model_validate(session)


@router.get("/sessions", response_model=SessionList)
async def list_sessions(novel_id: UUID, service: InterviewServiceDep) -> SessionList:
    """The novel's interviews for this user, open first then closed, newest first per state."""
    try:
        sessions = await service.list_sessions(novel_id)
    except InterviewRefusalError as error:
        raise _refusal(error) from None
    return SessionList(items=[SessionSummary.model_validate(session) for session in sessions])


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def read_session(session_id: UUID, service: InterviewServiceDep) -> SessionDetail:
    """The session with its transcript, up to ``TRANSCRIPT_READ_LIMIT`` turns, oldest first."""
    try:
        session = await service.read_session(session_id)
    except InterviewRefusalError as error:
        raise _refusal(error) from None
    return SessionDetail.model_validate(session)


@router.post("/sessions/{session_id}/turns", response_model=TurnReadback)
async def take_turn(
    session_id: UUID, payload: TurnCreate, service: InterviewServiceDep
) -> TurnReadback:
    """Take one turn; the refusal names why nothing (or only the marks) moved."""
    try:
        return await service.take_turn(session_id, payload)
    except InterviewRefusalError as error:
        raise _refusal(error) from None


@router.post("/sessions/{session_id}/close", response_model=SessionRead)
async def close_session(session_id: UUID, service: InterviewServiceDep) -> SessionRead:
    """End the interview; closing an already closed session answers it unchanged."""
    try:
        session = await service.close_session(session_id)
    except InterviewRefusalError as error:
        raise _refusal(error) from None
    return SessionRead.model_validate(session)
