"""HTTP surface. Parses, delegates to the service, streams; no logic here."""

import json
from collections.abc import AsyncGenerator
from logging import getLogger
from time import monotonic
from typing import Annotated
from uuid import UUID

from anyio import CancelScope
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.chat.schemas import ChatRequest, EmbeddingMismatchRead
from app.capabilities.chat.service import ChatService
from app.kernel.auth import current_user_id
from app.kernel.db.session import Session, get_session
from app.kernel.embeddings import EmbeddingProvider, get_embedding_provider
from app.kernel.llm import TextProvider, get_provider, provider_facts
from app.kernel.llm.audit import record_call
from app.kernel.llm.contract import CompletionRequest, Delta, Usage
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
    """Commit the call on a short session of the finalizer's own.

    A log row, not user data — plan §3.4's one exception to "no side effect
    after the response". Chat has no novel context until plan §9.2, so the
    row's novel_id stays NULL.

    ``answer`` may be partial; ``usage=None`` leaves token counts unknown.
    ``latency_ms`` is elapsed milliseconds. Provider configuration and database
    errors propagate to the finalizer.
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
) -> AsyncGenerator[str]:
    """Sources first, then the answer, then done.

    The sources go out before the first token so the reader can show what the
    answer was built from while it is still arriving. A provider that dies
    mid-stream ends with an error frame instead of done: the reader cannot see
    a traceback, and a silent close would look like a finished answer.
    Once provider streaming starts, finalization attempts an audit of the
    accumulated answer and latest usage (§3.4), including on interruption.
    Audit errors are suppressed and do not change the response frames.
    Closing at the initial sources frame makes no provider call or audit.
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
    status = "error"
    error: str | None = "stream interrupted"
    try:
        try:
            async for event in provider.stream(CompletionRequest.user(prompt)):
                if isinstance(event, Delta):
                    pieces.append(event.text)
                    yield f"data: {json.dumps({'delta': event.text})}\n\n"
                elif isinstance(event, Usage):
                    usage = event
        except Exception as failure:
            error = str(failure)
            logger.exception("chat stream failed")
            yield "event: error\ndata: {}\n\n"
        else:
            status = "ok"
            error = None
            yield "event: done\ndata: {}\n\n"
    finally:
        # A disconnect must not cancel the audit attempt.
        with CancelScope(shield=True):
            try:
                await _audit(
                    user_id=user_id,
                    prompt=prompt,
                    answer="".join(pieces),
                    usage=usage,
                    latency_ms=round((monotonic() - started) * 1000),
                    status=status,
                    error=error,
                )
            except Exception:
                logger.exception("chat audit failed")


@router.post(
    "/ask",
    response_class=FinalizingStreamingResponse,
    status_code=200,
    responses={
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
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
