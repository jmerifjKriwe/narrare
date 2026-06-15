"""Writing co-author routes — SSE-direct co-author revision endpoint.

Thin delegation layer (RULE-06): every route immediately delegates to
:class:`CoAuthorService`.  No business logic lives here.

Follows the same SSE-direct pattern as ``router_rewrite.py``.  The pipeline
computes a server-side diff after streaming completes and includes change
metadata in the final SSE event.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI path parameter type resolution

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare._app.rate_limits import AI_WRITE_LIMITER
from narrare.chapters.schemas import ChapterResponse
from narrare.writing._coauthor_sse import coauthor_event_stream
from narrare.writing.deps import get_coauthor_apply_service, get_coauthor_service
from narrare.writing.schemas_coauthor import (
    ApplyChangesRequest,
    CoAuthorFeedbackRequest,
    CoAuthorRequest,
)

router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/chapters/{chapter_id}/co-author",
    dependencies=[Depends(AI_WRITE_LIMITER)],
)
async def coauthor_chapter(
    chapter_id: uuid.UUID,
    novel_id: uuid.UUID,
    request: CoAuthorRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for co-author revision — create + stream in one call.

    Accepts a text selection with optional surrounding context and
    improvement focus areas (word_choice, sentence, dialogue, description).
    The AI generates a revised version, then a server-side diff is computed
    via :mod:`narrare_core.writing.change_engine`.  Change metadata is
    included in the final SSE event for the frontend to render diff controls.

    Uses ``LLMIntent.CO_AUTHOR`` for model routing.

    **SSE Event Stream:**

    1. ``context_meta`` event (CR-07 pattern) with KB context data.
    2. Text chunks: ``{"text": "..."}``
    3. Final event (last text chunk):
       - ``is_final: True``
       - ``usage: {prompt_tokens, completion_tokens, total_tokens}``
       - ``changes: [...]`` — list of change details
       - ``total_changes: N``
       - ``has_changes: True/False``
    4. ``data: [DONE]`` termination signal.
    """
    service = await get_coauthor_service(session, user_id, novel_id)

    # Pre-validate before starting SSE response to avoid RuntimeError
    # when ConflictError/NotFoundError fires after headers are sent.
    await service.validate_coauthor(chapter_id, novel_id, request)

    return StreamingResponse(
        coauthor_event_stream(service, chapter_id, novel_id, user_id, request),
        media_type="text/event-stream",
    )


@router.post("/chapters/{chapter_id}/co-author/apply")
async def apply_coauthor_changes(
    chapter_id: uuid.UUID,
    novel_id: uuid.UUID,
    request: ApplyChangesRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> ChapterResponse:
    """Apply accepted co-author changes to chapter content.

    Reconstructs the chapter text from original + accepted changes
    using :func:`narrare_core.writing.text_reconstructor.reconstruct_text`.
    Persists the updated content and records feedback for rejected changes.
    """
    service = await get_coauthor_apply_service(session)
    chapter = await service.apply_changes(chapter_id, novel_id, user_id, request)
    return ChapterResponse.model_validate(chapter)


@router.post("/chapters/{chapter_id}/co-author/feedback", status_code=204)
async def record_coauthor_feedback(
    chapter_id: uuid.UUID,
    novel_id: uuid.UUID,
    request: CoAuthorFeedbackRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> None:
    """Record batch feedback for co-author changes (LEARN-001).

    Accepts per-change accept/reject feedback and persists via
    the ``FeedbackCollector`` for preference learning.
    """
    service = await get_coauthor_apply_service(session)
    await service.record_feedback(request.request_id, request.feedback)
