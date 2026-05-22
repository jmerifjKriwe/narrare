"""Writing generation routes — REST + SSE endpoints.

Thin delegation layer (RULE-06): every route immediately delegates to
:class:`WritingService`.  No business logic lives here.
"""

from __future__ import annotations

import json
import uuid  # noqa: TC003 — needed at runtime for FastAPI path parameter type resolution
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep, SessionDep
from narrare.writing.deps import get_writing_service

if TYPE_CHECKING:
    from typing import Any

from narrare.writing.schemas import (
    AcceptResponse,
    GenerateRequest,
    GenerateResponse,
    RejectResponse,
    StopResponse,
)

router = APIRouter(prefix="/writing", tags=["writing"])


# -- Generation lifecycle ---------------------------------------------


@router.post("/chapters/{chapter_id}/generate", response_model=GenerateResponse)
async def start_generation(
    chapter_id: uuid.UUID,
    novel_id: uuid.UUID,
    request: GenerateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> GenerateResponse:
    """Start chapter generation — returns request_id, then stream via SSE."""
    service = await get_writing_service(session, user_id, novel_id)
    return await service.start_generation(chapter_id, novel_id, user_id, request)


@router.get("/generation/{request_id}/stream")
async def stream_generation(
    request_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for generated text chunks."""
    service = await get_writing_service(session, user_id)

    # Pre-validate before starting SSE response to avoid
    # RuntimeError when NotFoundError fires after headers sent.
    await service.validate_request_access(request_id, user_id)

    async def event_stream():
        async for chunk in service.stream_generation(request_id, user_id):
            data: dict[str, Any] = {"text": chunk.text}
            if chunk.is_final:
                data["is_final"] = True
            if chunk.usage is not None:
                data["usage"] = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
            yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/generation/{request_id}", response_model=StopResponse)
async def stop_generation(
    request_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StopResponse:
    """Stop an in-progress generation."""
    service = await get_writing_service(session, user_id)
    return await service.stop_generation(request_id, user_id)


@router.post("/generation/{request_id}/accept", response_model=AcceptResponse)
async def accept_draft(
    request_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    modified_text: str | None = None,
) -> AcceptResponse:
    """Accept a generated draft."""
    service = await get_writing_service(session, user_id)
    return await service.accept_draft(request_id, user_id, modified_text)


@router.post("/generation/{request_id}/reject", response_model=RejectResponse)
async def reject_draft(
    request_id: uuid.UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> RejectResponse:
    """Reject a generated draft."""
    service = await get_writing_service(session, user_id)
    return await service.reject_draft(request_id, user_id)
