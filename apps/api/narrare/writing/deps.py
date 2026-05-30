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

    from narrare.writing.coauthor_service import CoAuthorService
    from narrare.writing.extend_service import ExtendService
    from narrare.writing.rewrite_service import RewriteService
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
    from narrare._app.config import get_settings
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(project_id) if project_id else None,
    )
    config = replace(
        resolved.config,
        temperature=0.7,
        max_tokens=limits.output_limit,
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


async def get_extend_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> ExtendService:
    """Factory for ExtendService — resolves model config for EXTEND intent.

    Args:
        session: DB session for repository and settings lookups.
        user_id: Authenticated user identifier.
        project_id: Optional project/novel ID for project-level settings.

    Returns:
        Configured ExtendService ready for use.
    """
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.repository import UserSettingsRepository
    from narrare.writing.extend_service import ExtendService
    from narrare.writing.repository import GenerationRepository
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        LLMIntent.EXTEND,
        UUID(user_id),
        project_id,
    )
    from narrare._app.config import get_settings
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(project_id) if project_id else None,
    )
    config = replace(
        resolved.config,
        temperature=0.7,
        max_tokens=limits.output_limit,
    )

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

    return ExtendService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        tone_service=tone_service,
    )


async def get_rewrite_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> RewriteService:
    """Factory for RewriteService — resolves model config for REWRITE intent.

    Args:
        session: DB session for repository and settings lookups.
        user_id: Authenticated user identifier.
        project_id: Optional project/novel ID for project-level settings.

    Returns:
        Configured RewriteService ready for use.
    """
    from narrare._app.config import get_settings
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.repository import UserSettingsRepository
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.rewrite_service import RewriteService
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        LLMIntent.REWRITE,
        UUID(user_id),
        project_id,
    )
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(project_id) if project_id else None,
    )
    config = replace(
        resolved.config,
        temperature=0.7,
        max_tokens=limits.output_limit,
    )

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

    return RewriteService(
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
    from narrare.chapters.repository import ChapterRepository
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.writing.suggest_service import InlineSuggestService

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
    chapter_repo = ChapterRepository(session)

    return InlineSuggestService(
        registry=registry,
        composer=composer,
        config=config,
        chapter_repo=chapter_repo,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )


async def get_coauthor_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> CoAuthorService:
    """Factory for CoAuthorService — resolves model config for CO_AUTHOR intent.

    Args:
        session: DB session for repository and settings lookups.
        user_id: Authenticated user identifier.
        project_id: Optional project/novel ID for project-level settings.

    Returns:
        Configured CoAuthorService ready for use.
    """
    from narrare._app.config import get_settings
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing.coauthor_service import CoAuthorService
    from narrare.writing.repository import GenerationRepository
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.pipeline import WritingPipeline

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        LLMIntent.CO_AUTHOR,
        UUID(user_id),
        project_id,
    )
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(project_id) if project_id else None,
    )
    config = replace(
        resolved.config,
        temperature=0.7,
        max_tokens=limits.output_limit,
    )

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

    return CoAuthorService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
