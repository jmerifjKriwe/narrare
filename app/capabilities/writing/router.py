"""HTTP surface. Parses, delegates to the service, returns; no logic here."""

import json
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.writing.metadata import InvalidNovelUpdateError
from app.capabilities.writing.schemas import (
    ActivityRead,
    ChapterCreate,
    ChapterOrderUpdate,
    ChapterRead,
    ChapterUpdate,
    ExportDone,
    ExportRequest,
    FieldRefusalsRead,
    ImportRefusalsRead,
    ImportReportRead,
    NovelCreate,
    NovelRead,
    NovelUpdate,
    OrderMismatchRead,
    SceneCreate,
    SceneOrderMismatchRead,
    SceneOrderUpdate,
    SceneRead,
    SceneUpdate,
    WritingErrorRead,
)
from app.capabilities.writing.service import (
    MAX_ARCHIVE_BYTES,
    ArchiveInvalidError,
    ArchiveTooLargeError,
    FieldRefusedError,
    NotFoundError,
    OrderMismatchError,
    TargetNotEmptyError,
    WritingService,
)
from app.kernel.auth import SetupRequiredError, current_user_id
from app.kernel.context import DEFAULT_MAX_OUTPUT_TOKENS, BudgetImpossibleError
from app.kernel.contracts.models import Chapter, Scene
from app.kernel.db.session import get_session
from app.kernel.llm.audit import audited_stream
from app.kernel.llm.contract import CompletionRequest, Delta, Message
from app.kernel.llm.resolution import ResolvedProvider, resolve_provider
from app.kernel.llm.streaming import (
    DONE_FRAME,
    FinalizingStreamingResponse,
    error_events,
    failure_frame,
)
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
    except Exception as failure:
        logger.exception("continuation stream failed")
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


@router.get("/novels", response_model=list[NovelRead])
async def list_novels(service: ServiceDep, include_archived: bool = False) -> list[NovelRead]:
    """Return the current user's novels; archived books stay out of the
    main grid unless ``include_archived`` asks for them."""
    return list(await service.list_novels(include_archived=include_archived))


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
    return novel


@router.post(
    "/novels",
    response_model=NovelRead,
    status_code=201,
    responses={409: {"model": WritingErrorRead, "description": "Setup required"}},
)
async def create_novel(payload: NovelCreate, service: ServiceDep) -> NovelRead:
    """Create and return a novel; respond with HTTP 409 if setup is required."""
    try:
        novel = await service.create_novel(
            payload.title,
            genre=payload.genre,
            blurb=payload.blurb,
            target_words=payload.target_words,
        )
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return NovelRead.model_validate(novel)


@router.patch(
    "/novels/{novel_id}",
    response_model=NovelRead,
    responses={
        404: {"model": WritingErrorRead, "description": "Novel not found"},
        422: {"model": WritingErrorRead, "description": "An invalid field, named in `detail`"},
    },
)
async def update_novel(novel_id: UUID, payload: NovelUpdate, service: ServiceDep) -> NovelRead:
    """Correct a novel by hand: only the fields the body carries change.

    Return the novel with its derived counts; raise HTTP 404 for an absent
    or unowned novel, or HTTP 422 naming the field for a blank or over-long
    title, an over-long genre or author, a language that is over-long
    or not a BCP-47-ish code, a status outside the vocabulary, a series
    link that names no series of the user, or a volume without a series.
    """
    try:
        novel = await service.update_novel(novel_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except InvalidNovelUpdateError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return novel


@router.delete(
    "/novels/{novel_id}",
    status_code=204,
    responses={404: {"model": WritingErrorRead, "description": "Novel not found"}},
)
async def delete_novel(novel_id: UUID, service: ServiceDep) -> None:
    """Delete an owned novel. The novel-scoped foreign keys cascade: its
    chapters, entities, relations, suggestions and findings go with the
    row; the library's documents are not the novel's and stay.

    Raise HTTP 404 for an absent or unowned novel.
    """
    try:
        await service.delete_novel(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None


@router.post(
    "/novels/{novel_id}/duplicate",
    response_model=NovelRead,
    status_code=201,
    responses={
        404: {"model": WritingErrorRead, "description": "Novel not found"},
        409: {"model": WritingErrorRead, "description": "Setup required"},
    },
)
async def duplicate_novel(novel_id: UUID, service: ServiceDep) -> NovelRead:
    """Duplicate an owned novel: a new book with the same metadata and a
    full copy of its chapters, in one transaction.

    The copy is named ``„<title> (Kopie)"``, keeps the series link but no
    volume, and starts on the shelf — unarchived, never exported. Respond
    with HTTP 404 for an absent or unowned novel, or HTTP 409 if setup is
    required.
    """
    try:
        return await service.duplicate_novel(novel_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None


@router.get("/activity", response_model=ActivityRead)
async def activity(
    service: ServiceDep, days: Annotated[int, Query(ge=1, le=365)] = 30
) -> ActivityRead:
    """The atelier's daily words across all owned novels: the window's
    points (zero-days included), the streak of consecutive days with a
    nonzero net ending today or yesterday, the mean net words per day
    over the whole window, and today's net. ``days`` bounds the window
    to 1..365; the default is 30. The day boundary is the server's UTC
    date.
    """
    return await service.activity(days)


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
    # Note (#349): Starlette still buffers the whole multipart part into
    # memory on `archive.read()`; this pre-check avoids only the extra read
    # copy, not the upload buffering itself (framework limit).
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
    return list(chapters)


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


@router.put(
    "/novels/{novel_id}/chapter-order",
    status_code=204,
    responses={
        404: {"model": WritingErrorRead, "description": "Novel not found"},
        409: {
            "model": OrderMismatchRead,
            "description": "The body is not the book's current whole of chapter ids",
        },
    },
)
async def reorder_chapters(
    novel_id: UUID, payload: ChapterOrderUpdate, service: ServiceDep
) -> None:
    """Rewrite an owned novel's chapter order as one whole.

    The body carries every chapter of the novel in its new order. Respond
    with HTTP 204, HTTP 404 for an absent or unowned novel, or HTTP 409
    when the body is not the book's current whole — a chapter added or
    deleted in a second tab, or an id repeated — with
    ``detail.chapter_ids`` holding the stored ids in their position order:
    the arrangement the client reverts to.
    """
    try:
        await service.reorder_chapters(novel_id, payload.chapter_ids)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="novel not found") from None
    except OrderMismatchError as error:
        # A dict, not a sentence: the client reverts to the order these ids
        # name, and `code` is the stable key it localizes.
        raise HTTPException(
            status_code=409,
            detail={
                "code": "order_mismatch",
                "chapter_ids": [str(chapter_id) for chapter_id in error.current],
            },
        ) from None


@router.get(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    responses={404: {"model": WritingErrorRead, "description": "Chapter not found"}},
)
async def get_chapter(chapter_id: UUID, service: ServiceDep) -> ChapterRead:
    """Return an owned chapter with its scene-derived counts; respond with
    HTTP 404 when it is not found."""
    try:
        chapter = await service.read_chapter(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return chapter


@router.put(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    responses={404: {"model": WritingErrorRead, "description": "Chapter not found"}},
)
async def update_chapter(
    chapter_id: UUID, payload: ChapterUpdate, service: ServiceDep
) -> ChapterRead:
    """Update an owned chapter's title (its prose lives on scenes now);
    respond with HTTP 404 when it is not found."""
    try:
        chapter = await service.update_chapter(chapter_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return chapter


@router.delete(
    "/chapters/{chapter_id}",
    status_code=204,
    responses={404: {"model": WritingErrorRead, "description": "Chapter not found"}},
)
async def delete_chapter(chapter_id: UUID, service: ServiceDep) -> None:
    """Delete an owned chapter; the survivors close the gap, renumbered
    contiguously in the same transaction, and the novel's timestamp
    advances. The chapter's pending suggestions go with it; the novel's
    findings stay.

    Raise HTTP 404 for an absent or unowned chapter.
    """
    try:
        await service.delete_chapter(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None


@router.get(
    "/chapters/{chapter_id}/scenes",
    response_model=list[SceneRead],
    responses={404: {"model": WritingErrorRead, "description": "Chapter not found"}},
)
async def list_scenes(chapter_id: UUID, service: ServiceDep) -> list[SceneRead]:
    """List an owned chapter's scenes in position order, each with its derived
    word count; respond with HTTP 404 when the chapter is not found."""
    try:
        scenes = await service.list_scenes(chapter_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    return list(scenes)


@router.post(
    "/chapters/{chapter_id}/scenes",
    response_model=SceneRead,
    status_code=201,
    responses={
        404: {"model": WritingErrorRead, "description": "Chapter not found"},
        409: {"model": WritingErrorRead, "description": "Setup required"},
    },
)
async def create_scene(chapter_id: UUID, payload: SceneCreate, service: ServiceDep) -> SceneRead:
    """Create a scene under an owned chapter; return HTTP 404 for a missing
    chapter or HTTP 409 if setup is required."""
    try:
        scene = await service.create_scene(chapter_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    except SetupRequiredError:
        raise HTTPException(status_code=409, detail="setup required") from None
    return scene


@router.put(
    "/chapters/{chapter_id}/scene-order",
    status_code=204,
    responses={
        404: {"model": WritingErrorRead, "description": "Chapter not found"},
        409: {
            "model": SceneOrderMismatchRead,
            "description": "The body is not the chapter's current whole of scene ids",
        },
    },
)
async def reorder_scenes(chapter_id: UUID, payload: SceneOrderUpdate, service: ServiceDep) -> None:
    """Rewrite an owned chapter's scene order as one whole.

    The body carries every scene of the chapter in its new order. Respond
    with HTTP 204, HTTP 404 for an absent or unowned chapter, or HTTP 409
    when the body is not the chapter's current whole — a scene added or
    deleted in a second tab, or an id repeated — with ``detail.scene_ids``
    holding the stored ids in their position order: the arrangement the
    client reverts to.
    """
    try:
        await service.reorder_scenes(chapter_id, payload.ids)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="chapter not found") from None
    except OrderMismatchError as error:
        # A dict, not a sentence: the client reverts to the order these ids
        # name, and `code` is the stable key it localizes.
        raise HTTPException(
            status_code=409,
            detail={
                "code": "order_mismatch",
                "scene_ids": [str(scene_id) for scene_id in error.current],
            },
        ) from None


@router.get(
    "/scenes/{scene_id}",
    response_model=SceneRead,
    responses={404: {"model": WritingErrorRead, "description": "Scene not found"}},
)
async def get_scene(scene_id: UUID, service: ServiceDep) -> SceneRead:
    """Return an owned scene with its derived word count; respond with HTTP
    404 when it is not found."""
    try:
        scene = await service.read_scene(scene_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="scene not found") from None
    return scene


@router.put(
    "/scenes/{scene_id}",
    response_model=SceneRead,
    responses={404: {"model": WritingErrorRead, "description": "Scene not found"}},
)
async def update_scene(scene_id: UUID, payload: SceneUpdate, service: ServiceDep) -> SceneRead:
    """Update an owned scene: only the fields the body carries change.

    Respond with HTTP 404 when it is not found, or HTTP 422 for an over-long
    title or label.
    """
    try:
        scene = await service.update_scene(scene_id, payload)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="scene not found") from None
    return scene


@router.delete(
    "/scenes/{scene_id}",
    status_code=204,
    responses={404: {"model": WritingErrorRead, "description": "Scene not found"}},
)
async def delete_scene(scene_id: UUID, service: ServiceDep) -> None:
    """Delete an owned scene; the survivors close the gap, renumbered
    contiguously in the same transaction, and the novel's timestamp
    advances. Always allowed — an empty chapter is a real state (D16).

    Raise HTTP 404 for an absent or unowned scene.
    """
    try:
        await service.delete_scene(scene_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="scene not found") from None


@router.post(
    "/scenes/{scene_id}/continue",
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
        404: {"model": WritingErrorRead, "description": "Scene not found"},
    },
)
async def continue_scene(
    scene_id: UUID, service: ServiceDep, user_id: UserDep
) -> FinalizingStreamingResponse:
    """Stream a continuation for an owned scene; return HTTP 404 when it is not found.

    The unit is the scene (W4 §5): the context is the active scene's tail plus
    the book's earlier scenes nearest first. The SSE contract is the chapter
    endpoint's own, unchanged — the same frames, headers and coded refusals;
    only the unit and the context assembly moved onto scenes.
    """
    # Resolution reads the user's profiles on the request's own session, so it
    # must run before the connection goes back. A profile whose key its tier
    # can no longer produce ends the stream with the coded error frame a dead
    # provider gets — no call ran, so no audit row.
    try:
        resolved = await resolve_provider(service.session, user_id, "writing.continuation")
    except KeyUnavailableError:
        logger.exception("continuation provider resolution failed")
        return FinalizingStreamingResponse(
            error_events("key-unavailable"), media_type="text/event-stream", headers=SSE_HEADERS
        )
    # The builder sizes its slices from the resolved facts; a pair whose output
    # reserve fills the window refused there — mapped like the lost key above:
    # the one coded error frame, no provider call, no audit row. A prompt the
    # effective chain refuses (an override whose frame cannot hold its budget)
    # is mapped the same way, refused by name and never truncated.
    try:
        prompt = await service.continuation_prompt(
            scene_id,
            context_window=resolved.context_window,
            max_output_tokens=resolved.max_output_tokens,
            model=resolved.model,
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="scene not found") from None
    except BudgetImpossibleError:
        logger.exception("continuation budget refused")
        return FinalizingStreamingResponse(
            error_events("prompt-refused", reason="budget"),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )
    except PromptRenderError:
        logger.exception("continuation prompt refused")
        return FinalizingStreamingResponse(
            error_events("prompt-refused"), media_type="text/event-stream", headers=SSE_HEADERS
        )
    # The audit names the novel, so read its id before the response starts,
    # while the request's session is still open — one scalar, scoped to the
    # owner continuation_prompt already proved (plan §3.4). The scene reaches
    # its novel through the chapter it hangs off.
    novel_id = await service.session.scalar(
        select(Chapter.novel_id)
        .join(Scene, Scene.chapter_id == Chapter.id)
        .where(Scene.id == scene_id, Scene.user_id == user_id)
    )
    # The pooled connection goes back before the provider stream holds the
    # response open: nothing reads the database during the stream.
    await service.session.close()
    return FinalizingStreamingResponse(
        _continuation_events(resolved, prompt, novel_id, user_id),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
