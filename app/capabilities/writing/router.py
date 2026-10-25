"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

import json
from collections.abc import AsyncGenerator
from logging import getLogger
from time import monotonic
from typing import Annotated
from uuid import UUID

from anyio import CancelScope
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.writing.schemas import (
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
    NovelCreate,
    NovelRead,
)
from app.capabilities.writing.service import NotFoundError, WritingService
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.contracts.models import Chapter
from app.kernel.db.session import Session, get_session
from app.kernel.llm import TextProvider, get_provider, provider_facts
from app.kernel.llm.audit import record_call
from app.kernel.llm.contract import CompletionRequest, Delta, Usage
from app.kernel.llm.streaming import FinalizingStreamingResponse

router = APIRouter(prefix="/api/writing", tags=["writing"])

logger = getLogger("narrare")

SSE_HEADERS = {"Cache-Control": "no-cache"}

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> WritingService:
    """Build the writing service with the request session and current owner."""
    return WritingService(session, user_id)


ServiceDep = Annotated[WritingService, Depends(_service)]
ProviderDep = Annotated[TextProvider, Depends(get_provider)]


async def _audit(
    *,
    user_id: UUID,
    novel_id: UUID | None,
    prompt: str,
    answer: str,
    usage: Usage | None,
    latency_ms: int,
    status: str,
    error: str | None = None,
) -> None:
    """Record the call on a short session of the finalizer's own.

    A log row, not user data — plan §3.4's one exception to "no side effect
    after the response": the stream is over, and the audit cannot ride a
    request transaction that no longer exists.
    """
    kind, model = provider_facts()
    async with Session() as session:
        await record_call(
            session,
            user_id=user_id,
            task_key="writing.continuation",
            provider_kind=kind,
            model=model,
            latency_ms=latency_ms,
            status=status,
            prompt_text=prompt,
            response_text=answer,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            novel_id=novel_id,
            error=error,
        )
        await session.commit()


async def _continuation_events(
    provider: TextProvider, prompt: str, novel_id: UUID | None, user_id: UUID
) -> AsyncGenerator[str]:
    """Deltas, then done — or an error frame if the provider dies mid-stream.

    The editor appends what arrived and autosaves it; a silent close would look
    like a finished continuation. However the stream ends, the call is audited
    after the last frame (§3.4): success and failure alike leave their row.
    """
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
            logger.exception("continuation stream failed")
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
                    novel_id=novel_id,
                    prompt=prompt,
                    answer="".join(pieces),
                    usage=usage,
                    latency_ms=round((monotonic() - started) * 1000),
                    status=status,
                    error=error,
                )
            except Exception:
                logger.exception("continuation audit failed")


@router.get("/novels", response_model=list[NovelRead])
async def list_novels(service: ServiceDep) -> list[NovelRead]:
    """Return the current user's novels."""
    return [NovelRead.model_validate(novel) for novel in await service.list_novels()]


@router.get("/novels/{novel_id}", response_model=NovelRead)
async def get_novel(novel_id: UUID, service: ServiceDep) -> NovelRead:
    """Return an owned novel; respond with HTTP 404 when it is not found."""
    try:
        novel = await service.get_novel(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return NovelRead.model_validate(novel)


@router.post("/novels", response_model=NovelRead, status_code=201)
async def create_novel(payload: NovelCreate, service: ServiceDep) -> NovelRead:
    """Create and return a novel; respond with HTTP 409 if setup is required."""
    try:
        novel = await service.create_novel(payload.title, genre=payload.genre, blurb=payload.blurb)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return NovelRead.model_validate(novel)


@router.get("/novels/{novel_id}/chapters", response_model=list[ChapterRead])
async def list_chapters(novel_id: UUID, service: ServiceDep) -> list[ChapterRead]:
    """List chapters of an owned novel; respond with HTTP 404 when it is not found."""
    try:
        chapters = await service.list_chapters(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return [ChapterRead.model_validate(chapter) for chapter in chapters]


@router.post("/novels/{novel_id}/chapters", response_model=ChapterRead, status_code=201)
async def create_chapter(
    novel_id: UUID, payload: ChapterCreate, service: ServiceDep
) -> ChapterRead:
    """Create a chapter; return HTTP 404 for a missing novel or HTTP 409 if setup is required."""
    try:
        chapter = await service.create_chapter(novel_id, payload.title)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return ChapterRead.model_validate(chapter)


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
async def get_chapter(chapter_id: UUID, service: ServiceDep) -> ChapterRead:
    """Return an owned chapter; respond with HTTP 404 when it is not found."""
    try:
        chapter = await service.get_chapter(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return ChapterRead.model_validate(chapter)


@router.put("/chapters/{chapter_id}", response_model=ChapterRead)
async def update_chapter(
    chapter_id: UUID, payload: ChapterUpdate, service: ServiceDep
) -> ChapterRead:
    """Update an owned chapter; respond with HTTP 404 when it is not found."""
    try:
        chapter = await service.update_chapter(chapter_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return ChapterRead.model_validate(chapter)


@router.post("/chapters/{chapter_id}/continue")
async def continue_chapter(
    chapter_id: UUID, service: ServiceDep, provider: ProviderDep, user_id: UserDep
) -> FinalizingStreamingResponse:
    """Stream a continuation for an owned chapter; return HTTP 404 when it is not found."""
    try:
        prompt = await service.continuation_prompt(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    # The audit names the novel, so read its id before the response starts,
    # while the request's session is still open — one scalar, scoped to the
    # owner continuation_prompt already proved (plan §3.4).
    novel_id = await service.session.scalar(
        select(Chapter.novel_id).where(Chapter.id == chapter_id, Chapter.user_id == user_id)
    )
    # The pooled connection goes back before the provider stream holds the
    # response open: nothing reads the database during the stream.
    await service.session.close()
    return FinalizingStreamingResponse(
        _continuation_events(provider, prompt, novel_id, user_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
