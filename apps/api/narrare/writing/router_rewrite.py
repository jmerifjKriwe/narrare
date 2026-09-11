"""Writing rewrite routes — SSE-direct selection rewrite endpoint.

Thin delegation layer (RULE-06): every route immediately delegates to
:class:`RewriteService`.  No business logic lives here.

Split from ``router.py`` per RULE-04 (the main router is at its 150-line
limit).  Follows the same SSE-direct pattern as ``/extend``.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare._app.observability import enrich_sse_data
from narrare._app.rate_limits import AI_WRITE_LIMITER
from narrare.writing.deps import get_rewrite_service
from narrare.writing.schemas_rewrite import RewriteRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/chapters/{chapter_id}/rewrite",
    dependencies=[Depends(AI_WRITE_LIMITER)],
)
async def rewrite_chapter(
    chapter_id: uuid.UUID,
    novel_id: uuid.UUID,
    request: RewriteRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for selection rewrite — create + stream in one call.

    Accepts a text selection with optional surrounding context and returns
    AI-generated rewrite alternatives streamed via SSE.  Each alternative
    is wrapped in ``<alternative>`` tags.  The final SSE event includes
    ``request_id`` for use with accept/reject endpoints.

    Uses ``LLMIntent.REWRITE`` for model routing.  The number of
    alternatives is controlled by ``request.count`` (1-3).
    """
    service = await get_rewrite_service(session, user_id, novel_id)

    # Pre-validate before starting SSE response to avoid RuntimeError
    # when ConflictError/NotFoundError fires after headers are sent.
    # user_id threads the S6 ownership gate (foreign ≡ unknown → 404).
    await service.validate_rewrite(chapter_id, novel_id, request, user_id=user_id)

    async def event_stream() -> AsyncIterator[str]:
        async for chunk in service.stream_rewrite(
            chapter_id,
            novel_id,
            user_id,
            request,
        ):
            # Context metadata event (CR-07: sent as first event before text)
            if chunk.context_meta is not None:
                meta_data: dict[str, Any] = {"type": "context_meta"}
                meta_data.update(chunk.context_meta)
                yield f"data: {json.dumps(enrich_sse_data(meta_data))}\n\n"
                continue

            # Normal text chunk — <alternative> tags are preserved as raw text
            data: dict[str, Any] = {"text": chunk.text}
            if chunk.is_final:
                data["is_final"] = True
            if chunk.usage is not None:
                data["usage"] = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
