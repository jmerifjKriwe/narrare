"""Writing generation routes — REST + SSE endpoints.

Thin delegation layer (RULE-06): every route immediately delegates to
:class:`WritingService`.  No business logic lives here.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import (
    CurrentUserIdDep,
    SessionDep,
    get_composer,
    get_gateway,
    get_model_routing_resolver,
)
from narrare.writing.schemas import (
    AcceptResponse,
    GenerateRequest,
    GenerateResponse,
    RejectResponse,
    StopResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.service import WritingService

router = APIRouter(prefix="/writing", tags=["writing"])


async def get_writing_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> WritingService:
    """Factory for WritingService — resolves model config per user/intent."""
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.service import WritingService
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        LLMIntent.WRITE,
        UUID(user_id),
        project_id,
    )
    config = replace(resolved.config, temperature=0.7, max_tokens=4000)

    gateway = get_gateway()
    composer = get_composer()
    assembler = WritingContextAssembler()
    draft_processor = DraftProcessor()
    pipeline = WritingPipeline(
        gateway=gateway,
        composer=composer,
        context_assembler=assembler,
        draft_processor=draft_processor,
    )
    repo = GenerationRepository(session)

    return WritingService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )


# -- Generation lifecycle ---------------------------------------------


@router.post("/chapters/{chapter_id}/generate", response_model=GenerateResponse)
async def start_generation(
    chapter_id: UUID,
    novel_id: UUID,
    request: GenerateRequest,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> GenerateResponse:
    """Start chapter generation — returns request_id, then stream via SSE."""
    service = await get_writing_service(session, user_id, novel_id)
    return await service.start_generation(chapter_id, novel_id, user_id, request)


@router.get("/generation/{request_id}/stream")
async def stream_generation(
    request_id: UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StreamingResponse:
    """SSE stream for generated text chunks."""
    service = await get_writing_service(session, user_id)

    async def event_stream():
        async for chunk in service.stream_generation(request_id, user_id):
            yield f"data: {json.dumps({'text': chunk.text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/generation/{request_id}", response_model=StopResponse)
async def stop_generation(
    request_id: UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> StopResponse:
    """Stop an in-progress generation."""
    service = await get_writing_service(session, user_id)
    return await service.stop_generation(request_id, user_id)


@router.post("/generation/{request_id}/accept", response_model=AcceptResponse)
async def accept_draft(
    request_id: UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
    modified_text: str | None = None,
) -> AcceptResponse:
    """Accept a generated draft."""
    service = await get_writing_service(session, user_id)
    return await service.accept_draft(request_id, user_id, modified_text)


@router.post("/generation/{request_id}/reject", response_model=RejectResponse)
async def reject_draft(
    request_id: UUID,
    user_id: CurrentUserIdDep,
    session: SessionDep,
) -> RejectResponse:
    """Reject a generated draft."""
    service = await get_writing_service(session, user_id)
    return await service.reject_draft(request_id, user_id)
