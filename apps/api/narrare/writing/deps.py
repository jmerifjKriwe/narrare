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
    get_model_registry,
    get_model_routing_resolver,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.service import WritingService
    from narrare.writing.suggest_service import InlineSuggestService


async def get_writing_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
    intent: LLMIntent = LLMIntent.WRITE,
) -> WritingService:
    """Factory for WritingService — resolves model config per user/intent.

    Args:
        session: DB session for repository and settings lookups.
        user_id: Authenticated user identifier.
        project_id: Optional project/novel ID for project-level settings.
        intent: LLM operation intent.  Controls model routing and prompt
            selection.  Defaults to ``LLMIntent.WRITE`` (full chapter).
            Use ``LLMIntent.SUGGEST`` for lightweight inline suggestions.

    Returns:
        Configured WritingService ready for use.
    """
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.repository import UserSettingsRepository
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.service import WritingService
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        intent,
        UUID(user_id),
        project_id,
    )
    profile = resolved.config.token_limit_profile or "balanced"
    config = replace(
        resolved.config,
        temperature=0.7,
        max_tokens=resolved.config.resolve_output_limit(profile),
    )
    if intent == LLMIntent.SUGGEST:
        # SUGGEST uses a fixed 60-token limit — inline suggestions must be short
        # (UX constraint, not a profile concern).
        config = replace(config, temperature=0.3, max_tokens=60)

    registry = get_model_registry()
    composer = get_composer()
    assembler = WritingContextAssembler()
    draft_processor = DraftProcessor()
    pipeline = WritingPipeline(
        registry=registry,
        composer=composer,
        context_assembler=assembler,
        draft_processor=draft_processor,
    )
    repo = GenerationRepository(session)

    # Wire CustomToneService for custom tone resolution
    settings_repo = UserSettingsRepository(session)
    tone_service = CustomToneService(repo=settings_repo)

    return WritingService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        tone_service=tone_service,
    )


async def get_suggest_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> InlineSuggestService:
    """Factory for InlineSuggestService — resolves model config for SUGGEST."""
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.writing.suggest_service import InlineSuggestService
    from narrare_core.llm.intents import LLMIntent

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        LLMIntent.SUGGEST,
        UUID(user_id),
        project_id,
    )
    config = replace(resolved.config, temperature=0.3, max_tokens=60)

    registry = get_model_registry()
    composer = get_composer()

    return InlineSuggestService(
        registry=registry,
        composer=composer,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
