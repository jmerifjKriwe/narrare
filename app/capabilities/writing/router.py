"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

import json
from collections.abc import AsyncIterator
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
from app.kernel.db.session import get_session
from app.kernel.llm import TextProvider, get_provider
from app.kernel.llm.contract import CompletionRequest, Delta

router = APIRouter(prefix="/api/writing", tags=["writing"])

logger = getLogger("narrare")

SSE_HEADERS = {"Cache-Control": "no-cache"}

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> WritingService:
    return WritingService(session, user_id)


ServiceDep = Annotated[WritingService, Depends(_service)]
ProviderDep = Annotated[TextProvider, Depends(get_provider)]


async def _continuation_events(provider: TextProvider, prompt: str) -> AsyncIterator[str]:
    """Deltas, then done — or an error frame if the provider dies mid-stream.

    The editor appends what arrived and autosaves it; a silent close would look
    like a finished continuation.
    """
    try:
        async for event in provider.stream(CompletionRequest.user(prompt)):
            if isinstance(event, Delta):
                yield f"data: {json.dumps({'delta': event.text})}\n\n"
    except Exception:
        logger.exception("continuation stream failed")
        yield "event: error\ndata: {}\n\n"
        return
    yield "event: done\ndata: {}\n\n"


@router.get("/novels", response_model=list[NovelRead])
async def list_novels(service: ServiceDep) -> list[NovelRead]:
    return [NovelRead.model_validate(novel) for novel in await service.list_novels()]


@router.get("/novels/{novel_id}", response_model=NovelRead)
async def get_novel(novel_id: UUID, service: ServiceDep) -> NovelRead:
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
    try:
        chapters = await service.list_chapters(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return [ChapterRead.model_validate(chapter) for chapter in chapters]


@router.post("/novels/{novel_id}/chapters", response_model=ChapterRead, status_code=201)
async def create_chapter(
    novel_id: UUID, payload: ChapterCreate, service: ServiceDep
) -> ChapterRead:
    try:
        chapter = await service.create_chapter(novel_id, payload.title)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return ChapterRead.model_validate(chapter)


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
async def get_chapter(chapter_id: UUID, service: ServiceDep) -> ChapterRead:
    try:
        chapter = await service.get_chapter(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return ChapterRead.model_validate(chapter)


@router.put("/chapters/{chapter_id}", response_model=ChapterRead)
async def update_chapter(
    chapter_id: UUID, payload: ChapterUpdate, service: ServiceDep
) -> ChapterRead:
    try:
        chapter = await service.update_chapter(chapter_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return ChapterRead.model_validate(chapter)


@router.post("/chapters/{chapter_id}/continue")
async def continue_chapter(
    chapter_id: UUID, service: ServiceDep, provider: ProviderDep
) -> StreamingResponse:
    try:
        prompt = await service.continuation_prompt(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    # The pooled connection goes back before the provider stream holds the
    # response open: nothing reads the database during the stream.
    await service.session.close()
    return StreamingResponse(
        _continuation_events(provider, prompt),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
