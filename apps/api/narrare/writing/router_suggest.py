"""Writing suggest routes — SSE-direct inline suggestion endpoint.

Thin delegation layer (RULE-06): every route immediately delegates to
:class:`InlineSuggestService`.  No business logic lives here.

Split from ``router.py`` per RULE-04 (the main router is at its 150-line
limit).  Follows the same SSE-direct pattern as ``router_extend.py``.
"""

from __future__ import annotations

import json
import uuid  # noqa: TC003 — needed at runtime for FastAPI path parameter type resolution
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare._app.observability import enrich_sse_data
from narrare._app.rate_limits import AI_WRITE_LIMITER
from narrare.writing.deps import get_suggest_service
from narrare.writing.schemas import InlineSuggestRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/chapters/{chapter_id}/suggest",
    dependencies=[Depends(AI_WRITE_LIMITER)],
)
async def suggest_inline(
    chapter_id: uuid.UUID,
    request: InlineSuggestRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for inline ghost text suggestions.

    Accepts the user's current text context (split at cursor) and
    returns a short (1-3 sentence) completion streamed via SSE.
    Uses ``LLMIntent.SUGGEST`` for a lightweight, low-latency model.
    Maximum ~60 tokens per suggestion.

    Pre-validates chapter access before starting the SSE stream to
    avoid RuntimeError when validation errors fire after headers
    are sent.
    """
    suggest_service = await get_suggest_service(
        session,
        user_id,
        project_id=None,
    )

    # Pre-validate before starting SSE response to avoid RuntimeError
    # when NotFoundError/ValidationError fires after headers are sent.
    await suggest_service.validate_suggest(chapter_id, user_id, request)

    async def event_stream() -> AsyncIterator[str]:
        async for chunk in suggest_service.suggest_inline(
            chapter_id,
            user_id,
            request,
        ):
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
