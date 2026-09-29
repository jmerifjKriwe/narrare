"""Writing story-suggest routes — SSE endpoint for Writer's Unblock.

Thin delegation layer (RULE-06): the route immediately delegates to
:class:`StorySuggestService`.  No business logic lives here.

Follows the same SSE-direct pattern as ``router_suggest.py``.  The service
yields structured :class:`StorySuggestStreamEvent` objects (not text chunks),
so the SSE stream emits a single ``"suggestions"`` event followed by a
``"done"`` termination event.

See WRITE-009 (Writer's Unblock Tools).
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
from narrare.writing.deps_story_suggest import get_story_suggest_service
from narrare.writing.schemas_story_suggest import StorySuggestRequest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/writing", tags=["writing"])


@router.post(
    "/story-suggest/{novel_id}",
    dependencies=[Depends(AI_WRITE_LIMITER)],
)
async def story_suggest(
    novel_id: uuid.UUID,
    request: StorySuggestRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for story direction suggestions (Writer's Unblock).

    Accepts a novel ID and optional author instructions, then runs the
    :class:`StorySuggestAgent` to produce 3-5 distinct story suggestions.
    Uses ``LLMIntent.SUGGEST`` with ``context_mode="story_suggest"`` for
    model routing and prompt resolution.

    The pre-stream ``validate_suggest`` seam (ADR-086 L34) runs the
    uid-scoped novel-ownership gate (404) and the graceful first-use
    model resolution BEFORE the SSE stream starts, so the 404 fires with
    proper HTTP semantics instead of the RuntimeError that occurs when
    validation errors fire after headers.

    **SSE Event Stream:**

    1. ``"suggestions"`` event with the full suggestion list.
    2. ``"done"`` event (``is_final=True``).
    3. ``data: [DONE]`` termination signal.
    """
    service = await get_story_suggest_service(
        session=session,
        user_id=user_id,
        novel_id=novel_id,
    )

    # ADR-086 L34: pre-stream seam — the uid-scoped novel gate (404) and
    # the graceful first-use resolve run BEFORE the StreamingResponse is
    # constructed (pure delegation, RULE-06). Graceful (AI-optional): a
    # missing AI provider never raises here; the preserved no_model_config
    # outcome stays in-band exactly as before.
    await service.validate_suggest(novel_id, uuid.UUID(user_id))

    async def event_stream() -> AsyncIterator[str]:
        async for event in service.suggest(novel_id, uuid.UUID(user_id), request):
            data = event.model_dump(mode="json")
            yield f"data: {json.dumps(enrich_sse_data(data))}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
