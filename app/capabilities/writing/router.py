"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

import json
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.writing.schemas import (
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
    ExportDone,
    ExportRequest,
    FieldRefusalsRead,
    ImportRefusalsRead,
    ImportReportRead,
    NovelCreate,
    NovelRead,
    WritingErrorRead,
)
from app.capabilities.writing.service import (
    MAX_ARCHIVE_BYTES,
    ArchiveInvalidError,
    ArchiveTooLargeError,
    FieldRefusedError,
    NotFoundError,
    TargetNotEmptyError,
    WritingService,
)
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.context import DEFAULT_MAX_OUTPUT_TOKENS, BudgetImpossibleError
from app.kernel.contracts.models import Chapter
from app.kernel.db.session import get_session
from app.kernel.llm.audit import audited_stream
from app.kernel.llm.contract import CompletionRequest, Delta, Message
from app.kernel.llm.resolution import ResolvedProvider, resolve_provider
from app.kernel.llm.streaming import ERROR_FRAME, FinalizingStreamingResponse, error_events
from app.kernel.prompts import PromptRenderError
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


def _refusal(error: FieldRefusedError) -> HTTPException:
    """A refused field contract as a 422 naming each field — the settings
    router's answer, so the client learns exactly which input was refused."""
    return HTTPException(
        status_code=422,
        detail=[
            {"loc": ["body", field], "msg": str(error), "type": "value_error"}
            for field in error.fields
        ],
    )


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


@router.post(
    "/novels/{novel_id}/export",
    response_model=ExportDone,
    responses={
        404: {"model": WritingErrorRead, "description": "Novel not found"},
        409: {
            "description": "The target exists and is non-empty",
            "content": {
                "application/json": {
                    "example": {"detail": {"code": "target_not_empty", "path": "/home/me/export"}}
                }
            },
        },
        422: {
            "model": FieldRefusalsRead,
            "description": ("A missing, unwritable or file target path, named in `detail[].loc`"),
        },
    },
)
async def export_novel(
    novel_id: UUID, payload: ExportRequest, service: ServiceDep
) -> ExportDone | Response:
    """Export an owned novel as a ZIP download or into a directory on disk.

    The ZIP answer carries ``Content-Disposition: attachment`` named after the
    title's slug; the path answer is the receipt: where it went and how much.
    Respond with HTTP 404 for an absent or unowned novel, HTTP 409 when the
    target exists and is non-empty, or HTTP 422 naming the field for a
    missing, unwritable or file target path.
    """
    try:
        result = await service.export_novel(novel_id, payload.mode, payload.path)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except TargetNotEmptyError as error:
        raise HTTPException(
            status_code=409, detail={"code": "target_not_empty", "path": error.path}
        ) from None
    except FieldRefusedError as error:
        raise _refusal(error) from None
    if isinstance(result, tuple):
        slug, data = result
        return Response(
            content=data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
        )
    return result


@router.post(
    "/novels/import",
    response_model=ImportReportRead,
    status_code=201,
    responses={
        404: {"model": WritingErrorRead, "description": "Novel not found"},
        409: {
            "description": ("Setup is required (a new-novel import needs the user setup creates)"),
            "content": {
                "application/json": {
                    "examples": {
                        "setup_required": {"value": {"detail": "setup required"}},
                    }
                }
            },
        },
        413: {"description": "The archive is larger than 20 000 000 bytes"},
        422: {
            "model": ImportRefusalsRead,
            "description": (
                "A source contract break, named in `detail[].loc`, or an "
                "unreadable archive whose file is named in `detail.file`"
            ),
        },
    },
)
async def import_novel(
    service: ServiceDep,
    archive: Annotated[UploadFile | None, File()] = None,
    path: Annotated[str | None, Form()] = None,
    novel_id: Annotated[UUID | None, Form()] = None,
) -> ImportReportRead:
    """Import one archive as a new novel, or merged into an owned one.

    The archive arrives as an upload or as a server-side path — exactly one
    of the two. Respond with HTTP 404 for an absent or unowned target novel,
    HTTP 413 for an oversized archive, HTTP 422 naming the field for a
    source contract break or an unreachable path, HTTP 422 with the offending
    file named for an unreadable or malformed archive, or HTTP 409 for a
    new-novel import before setup (`setup required`).
    """
    # The cap is checked on the upload's reported size before `read()` loads
    # it; the service keeps the authoritative check on the actual bytes.
    if archive is not None and archive.size is not None and archive.size > MAX_ARCHIVE_BYTES:
        raise HTTPException(status_code=413, detail="archive too large")
    data = await archive.read() if archive is not None else None
    try:
        report = await service.import_novel(archive=data, path=path, novel_id=novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    except ArchiveTooLargeError:
        raise HTTPException(status_code=413, detail="archive too large") from None
    except ArchiveInvalidError as error:
        # A dict, not a sentence: the UI localizes this error and needs a code,
        # and `file` carries the archive-supplied path as a plain string.
        raise HTTPException(
            status_code=422,
            detail={"code": "archive_invalid", "file": error.file, "reason": error.reason},
        ) from None
    except FieldRefusedError as error:
        raise _refusal(error) from None
    return ImportReportRead.model_validate(report, from_attributes=True)


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
    # the one error frame, no provider call, no audit row. A prompt the
    # effective chain refuses (an override whose frame cannot hold its budget)
    # is mapped the same way, refused by name and never truncated.
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
    except PromptRenderError:
        logger.exception("continuation prompt refused")
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
