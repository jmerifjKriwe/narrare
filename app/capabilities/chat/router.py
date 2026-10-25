"""HTTP surface. Parses, delegates to the service, streams; no logic here."""

import json
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.chat.schemas import ChatRequest, EmbeddingMismatchRead
from app.capabilities.chat.service import ChatService
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from app.kernel.llm import TextProvider, get_provider
from app.kernel.llm.audit import audited_stream
from app.kernel.llm.contract import CompletionRequest, Delta
from app.kernel.llm.streaming import FinalizingStreamingResponse
from app.kernel.retrieval import EmbeddingMismatchError, Passage

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = getLogger("narrare")

SSE_HEADERS = {"Cache-Control": "no-cache"}

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]
EmbeddingsDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
ProviderDep = Annotated[TextProvider, Depends(get_provider)]


def _service(session: SessionDep, user_id: UserDep, embeddings: EmbeddingsDep) -> ChatService:
    """Build the chat service with the request session, owner, and embeddings."""
    return ChatService(session, user_id, embeddings)


ServiceDep = Annotated[ChatService, Depends(_service)]


async def _events(
    provider: TextProvider, prompt: str, passages: list[Passage], user_id: UUID
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
        provider, CompletionRequest.user(prompt), user_id=user_id, task_key="chat.ask"
    )
    try:
        async for event in events:
            if isinstance(event, Delta):
                yield f"data: {json.dumps({'delta': event.text})}\n\n"
    except Exception:
        logger.exception("chat stream failed")
        yield "event: error\ndata: {}\n\n"
    else:
        yield "event: done\ndata: {}\n\n"
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
    payload: ChatRequest, service: ServiceDep, provider: ProviderDep, user_id: UserDep
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
    # The pooled connection goes back before the provider stream holds the
    # response open: nothing reads the database during the stream.
    await service.session.close()
    return FinalizingStreamingResponse(
        _events(provider, prompt, passages, user_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
