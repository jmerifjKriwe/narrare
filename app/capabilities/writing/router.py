"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

import json
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.writing.schemas import (
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
    NovelCreate,
    NovelRead,
    WritingErrorRead,
)
from app.capabilities.writing.service import NotFoundError, WritingService
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.context import DEFAULT_MAX_OUTPUT_TOKENS, BudgetImpossibleError
from app.kernel.contracts.models import Chapter
from app.kernel.db.session import get_session
from app.kernel.llm.audit import audited_stream
from app.kernel.llm.contract import CompletionRequest, Delta, Message
from app.kernel.llm.resolution import ResolvedProvider, resolve_provider
from app.kernel.llm.streaming import ERROR_FRAME, FinalizingStreamingResponse, error_events
from app.kernel.secrets import KeyUnavailableError

router = APIRouter(prefix="/api/writing", tags=["writing"])

logger = getLogger("narrare")

SSE_HEADERS = {"Cache-Control": "no-cache"}

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[UUID, Depends(current_user_id)]


def _service(session: SessionDep, user_id: UserDep) -> WritingService:
    """Build the writing service with the request session and current owner."""
    return WritingService(session, user_id)


ServiceDep = Annotated[WritingService, Depends(_service)]


async def _continuation_events(
    resolved: ResolvedProvider, prompt: str, novel_id: UUID | None, user_id: UUID
) -> AsyncGenerator[str]:
    """Deltas, then done — or an error frame if the provider dies mid-stream.

    The editor appends what arrived and autosaves it; a silent close would look
    like a finished continuation. The request carries the wire facts: the
    resolved profile's temperature where it sets one, and ``max_tokens`` always
    — the output reservation is a wire cap, so the profile's value rides, or
    the kernel default when the facts leave it unset. However the stream ends
    — done, error, disconnect, cancel — the call is audited (§3.4): success and
    failure alike leave their row, a disconnect records "stream interrupted".
    """
    request = CompletionRequest(
        messages=(Message(role="user", content=prompt),),
        temperature=resolved.temperature,
        max_tokens=(
            resolved.max_output_tokens
            if resolved.max_output_tokens is not None
            else DEFAULT_MAX_OUTPUT_TOKENS
        ),
    )
    events = audited_stream(
        resolved,
        request,
        user_id=user_id,
        task_key="writing.continuation",
        novel_id=novel_id,
    )
    try:
        async for event in events:
            if isinstance(event, Delta):
                yield f"data: {json.dumps({'delta': event.text})}\n\n"
    except Exception:
        logger.exception("continuation stream failed")
        yield ERROR_FRAME
    else:
        yield "event: done\ndata: {}\n\n"
    finally:
        # The inner finalizer must run deterministically: relying on the loop's
        # async-generator finalizer would lose the audit row on a disconnect.
        await events.aclose()


@router.get("/novels", response_model=list[NovelRead])
async def list_novels(service: ServiceDep) -> list[NovelRead]:
    """Return the current user's novels."""
    return [NovelRead.model_validate(novel) for novel in await service.list_novels()]


@router.get(
    "/novels/{novel_id}",
    response_model=NovelRead,
    responses={404: {"model": WritingErrorRead, "description": "Novel not found"}},
)
async def get_novel(novel_id: UUID, service: ServiceDep) -> NovelRead:
    """Return an owned novel; respond with HTTP 404 when it is not found."""
    try:
        novel = await service.get_novel(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return NovelRead.model_validate(novel)


@router.post(
    "/novels",
    response_model=NovelRead,
    status_code=201,
    responses={409: {"model": WritingErrorRead, "description": "Setup required"}},
)
async def create_novel(payload: NovelCreate, service: ServiceDep) -> NovelRead:
    """Create and return a novel; respond with HTTP 409 if setup is required."""
    try:
        novel = await service.create_novel(payload.title, genre=payload.genre, blurb=payload.blurb)
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return NovelRead.model_validate(novel)


@router.get(
    "/novels/{novel_id}/chapters",
    response_model=list[ChapterRead],
    responses={404: {"model": WritingErrorRead, "description": "Novel not found"}},
)
async def list_chapters(novel_id: UUID, service: ServiceDep) -> list[ChapterRead]:
    """List chapters of an owned novel; respond with HTTP 404 when it is not found."""
    try:
        chapters = await service.list_chapters(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    return [ChapterRead.model_validate(chapter) for chapter in chapters]


@router.post(
    "/novels/{novel_id}/chapters",
    response_model=ChapterRead,
    status_code=201,
    responses={
        404: {"model": WritingErrorRead, "description": "Novel not found"},
        409: {"model": WritingErrorRead, "description": "Setup required"},
    },
)
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


@router.get(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    responses={404: {"model": WritingErrorRead, "description": "Chapter not found"}},
)
async def get_chapter(chapter_id: UUID, service: ServiceDep) -> ChapterRead:
    """Return an owned chapter; respond with HTTP 404 when it is not found."""
    try:
        chapter = await service.get_chapter(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return ChapterRead.model_validate(chapter)


@router.put(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    responses={404: {"model": WritingErrorRead, "description": "Chapter not found"}},
)
async def update_chapter(
    chapter_id: UUID, payload: ChapterUpdate, service: ServiceDep
) -> ChapterRead:
    """Update an owned chapter; respond with HTTP 404 when it is not found."""
    try:
        chapter = await service.update_chapter(chapter_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return ChapterRead.model_validate(chapter)


@router.post(
    "/chapters/{chapter_id}/continue",
    response_class=FinalizingStreamingResponse,
    status_code=200,
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "description": (
                        "Server-sent events: data frames of the continuation,"
                        " then one terminal event: done or error."
                    ),
                }
            }
        },
        404: {"model": WritingErrorRead, "description": "Chapter not found"},
    },
)
async def continue_chapter(
    chapter_id: UUID, service: ServiceDep, user_id: UserDep
) -> FinalizingStreamingResponse:
    """Stream a continuation for an owned chapter; return HTTP 404 when it is not found."""
    # Resolution reads the user's profiles on the request's own session, so it
    # must run before the connection goes back. A profile whose key its tier
    # can no longer produce ends the stream with the error frame a dead
    # provider gets — no call ran, so no audit row.
    try:
        resolved = await resolve_provider(service.session, user_id, "writing.continuation")
    except KeyUnavailableError:
        logger.exception("continuation provider resolution failed")
        return FinalizingStreamingResponse(
            error_events(), media_type="text/event-stream", headers=SSE_HEADERS
        )
    # The builder sizes its slices from the resolved facts; a pair whose output
    # reserve fills the window refused there — mapped like the lost key above:
    # the one error frame, no provider call, no audit row.
    try:
        prompt = await service.continuation_prompt(
            chapter_id,
            context_window=resolved.context_window,
            max_output_tokens=resolved.max_output_tokens,
            model=resolved.model,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    except BudgetImpossibleError:
        logger.exception("continuation budget refused")
        return FinalizingStreamingResponse(
            error_events(), media_type="text/event-stream", headers=SSE_HEADERS
        )
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
        _continuation_events(resolved, prompt, novel_id, user_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
