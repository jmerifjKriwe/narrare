"""HTTP surface. Parses, delegates to the service, streams; no logic here."""

import json
from collections.abc import AsyncIterator
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.chat.schemas import ChatRequest
from app.capabilities.chat.service import ChatService
from app.kernel.auth import current_user_id
from app.kernel.db.session import get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from app.kernel.llm import TextProvider, get_provider
from app.kernel.retrieval import EmbeddingMismatchError, Passage

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = getLogger("narrare")

SSE_HEADERS = {"Cache-Control": "no-cache"}

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]
EmbeddingsDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
ProviderDep = Annotated[TextProvider, Depends(get_provider)]


def _service(session: SessionDep, user_id: UserDep, embeddings: EmbeddingsDep) -> ChatService:
    return ChatService(session, user_id, embeddings)


ServiceDep = Annotated[ChatService, Depends(_service)]


async def _events(
    provider: TextProvider, prompt: str, passages: list[Passage]
) -> AsyncIterator[str]:
    """Sources first, then the answer, then done.

    The sources go out before the first token so the reader can show what the
    answer was built from while it is still arriving. A provider that dies
    mid-stream ends with an error frame instead of done: the reader cannot see
    a traceback, and a silent close would look like a finished answer.
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
    try:
        async for delta in provider.stream(prompt):
            yield f"data: {json.dumps({'delta': delta})}\n\n"
    except Exception:
        logger.exception("chat stream failed")
        yield "event: error\ndata: {}\n\n"
        return
    yield "event: done\ndata: {}\n\n"


@router.post("/ask")
async def ask(
    payload: ChatRequest, service: ServiceDep, provider: ProviderDep
) -> StreamingResponse:
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
    return StreamingResponse(
        _events(provider, prompt, passages),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
