"""Writing style-variant routes — SSE-direct regeneration endpoint (CR-AUFG-07-22).

Thin delegation layer (RULE-06): every route immediately delegates to
:class:`StyleVariantService`.  No business logic lives here.

Follows the same SSE-direct pattern as ``router_rewrite.py``.
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
from narrare.writing.deps import get_style_variant_service
from narrare.writing.schemas_style_variants import StyleVariantRegenerateRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/chapters/{chapter_id}/style-variants/regenerate",
    dependencies=[Depends(AI_WRITE_LIMITER)],
)
async def regenerate_style_variant(
    chapter_id: uuid.UUID,
    novel_id: uuid.UUID,
    request: StyleVariantRegenerateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for style-variant regeneration — create + stream in one call.

    Accepts an existing AI output (source_text) with a style variant and
    returns a regenerated version streamed via SSE.  The output is wrapped
    in an ``<alternative>`` tag (count=1).  The final SSE event includes
    ``is_final`` for use with accept/reject endpoints.

    Model/provider/token settings resolve through the existing REWRITE cascade;
    the variant never changes providers.
    """
    service = await get_style_variant_service(session, user_id, novel_id)

    # Pre-validate before starting SSE response to avoid RuntimeError
    # when ConflictError/NotFoundError fires after headers are sent.
    await service.validate_variant(chapter_id, novel_id, request)

    async def event_stream() -> AsyncIterator[str]:
        async for chunk in service.stream_variant(
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

            # Normal text chunk — <alternative> tags preserved as raw text
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
