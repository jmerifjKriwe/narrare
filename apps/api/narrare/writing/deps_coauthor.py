"""Writing module dependency injection — coauthor service factories."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.kb.relationship_repository import RelationshipRepository
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.coauthor_apply_service import CoAuthorApplyService
    from narrare.writing.coauthor_service import CoAuthorService


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
    from narrare.writing.deps_pipeline import create_pipeline
    from narrare.writing.repository import GenerationRepository
    from narrare_core.writing.draft_processor import DraftProcessor

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

    draft_processor = DraftProcessor()
    pipeline = create_pipeline(draft_processor, tier_overrides=limits.tier_percentages)
    repo = GenerationRepository(session)
    relationship_repo = RelationshipRepository(session)

    return CoAuthorService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        relationship_repo=relationship_repo,
        max_selection_words=limits.max_selection_words,
    )


async def get_coauthor_apply_service(
    session: AsyncSession,
) -> CoAuthorApplyService:
    """Lightweight factory — repos only, no pipeline or model config."""
    from narrare.chapters.repository import ChapterRepository
    from narrare.writing.coauthor_apply_service import CoAuthorApplyService
    from narrare.writing.repository import GenerationRepository

    return CoAuthorApplyService(
        repo=GenerationRepository(session),
        chapter_repo=ChapterRepository(session),
    )
