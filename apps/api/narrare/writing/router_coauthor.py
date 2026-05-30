"""Writing co-author routes — SSE-direct co-author revision endpoint.

Thin delegation layer (RULE-06): every route immediately delegates to
:class:`CoAuthorService`.  No business logic lives here.

Follows the same SSE-direct pattern as ``router_rewrite.py``.  The pipeline
computes a server-side diff after streaming completes and includes change
metadata in the final SSE event.
"""

from __future__ import annotations

import json
import uuid  # noqa: TC003 — needed at runtime for FastAPI path parameter type resolution
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.writing.deps import get_coauthor_service
from narrare.writing.schemas_coauthor import CoAuthorRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

router = APIRouter(prefix="/writing", tags=["writing"])


@router.post("/chapters/{chapter_id}/co-author")
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

    async def event_stream() -> AsyncIterator[str]:
        async for chunk in service.stream_coauthor(
            chapter_id,
            novel_id,
            user_id,
            request,
        ):
            # CR-07 context metadata event — always the first chunk from
            # the pipeline (is_final=False, context_meta has KB context data).
            if chunk.context_meta is not None and not chunk.is_final:
                meta_data: dict[str, Any] = {"type": "context_meta"}
                meta_data.update(chunk.context_meta)
                yield f"data: {json.dumps(meta_data)}\n\n"
                continue

            # Normal text chunk (includes the final chunk with diff metadata)
            data: dict[str, Any] = {"text": chunk.text}
            if chunk.is_final:
                data["is_final"] = True
                # Co-author diff metadata from pipeline_coauthor
                if chunk.context_meta is not None:
                    for key in ("changes", "total_changes", "has_changes", "reasoning"):
                        if key in chunk.context_meta:
                            data[key] = chunk.context_meta[key]
            if chunk.usage is not None:
                data["usage"] = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
