"""HTTP surface. Parses, delegates to the service, streams; no logic here."""

import json
from collections.abc import AsyncIterator
from logging import getLogger
from time import monotonic
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.chat.schemas import ChatRequest
from app.capabilities.chat.service import ChatService
from app.kernel.auth import current_user_id
from app.kernel.db.session import Session, get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from app.kernel.llm import TextProvider, get_provider, provider_facts
from app.kernel.llm.audit import record_call
from app.kernel.llm.contract import CompletionRequest, Delta, Usage
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


async def _audit(
    *,
    user_id: UUID,
    prompt: str,
    answer: str,
    usage: Usage | None,
    latency_ms: int,
    status: str,
    error: str | None = None,
) -> None:
    """Record the call on a short session of the finalizer's own.

    A log row, not user data — plan §3.4's one exception to "no side effect
    after the response". Chat has no novel context until plan §9.2, so the
    row's novel_id stays NULL.
    """
    kind, model = provider_facts()
    async with Session() as session:
        await record_call(
            session,
            user_id=user_id,
            task_key="chat.ask",
            provider_kind=kind,
            model=model,
            latency_ms=latency_ms,
            status=status,
            prompt_text=prompt,
            response_text=answer,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            error=error,
        )
        await session.commit()


async def _events(
    provider: TextProvider, prompt: str, passages: list[Passage], user_id: UUID
) -> AsyncIterator[str]:
    """Sources first, then the answer, then done.

    The sources go out before the first token so the reader can show what the
    answer was built from while it is still arriving. A provider that dies
    mid-stream ends with an error frame instead of done: the reader cannot see
    a traceback, and a silent close would look like a finished answer. However
    the stream ends, the call is audited after the last frame (§3.4).
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
    pieces: list[str] = []
    usage: Usage | None = None
    started = monotonic()
    try:
        async for event in provider.stream(CompletionRequest.user(prompt)):
            if isinstance(event, Delta):
                pieces.append(event.text)
                yield f"data: {json.dumps({'delta': event.text})}\n\n"
            elif isinstance(event, Usage):
                usage = event
    except Exception as failure:
        logger.exception("chat stream failed")
        yield "event: error\ndata: {}\n\n"
        await _audit(
            user_id=user_id,
            prompt=prompt,
            answer="".join(pieces),
            usage=usage,
            latency_ms=round((monotonic() - started) * 1000),
            status="error",
            error=str(failure),
        )
        return
    yield "event: done\ndata: {}\n\n"
    await _audit(
        user_id=user_id,
        prompt=prompt,
        answer="".join(pieces),
        usage=usage,
        latency_ms=round((monotonic() - started) * 1000),
        status="ok",
    )


@router.post("/ask")
async def ask(
    payload: ChatRequest, service: ServiceDep, provider: ProviderDep, user_id: UserDep
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
        _events(provider, prompt, passages, user_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
