"""Writing module dependency injection — factories and resolvers.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies import (
    get_composer,
    get_gateway,
    get_model_routing_resolver,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.service import WritingService


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
