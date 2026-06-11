"""Writing module dependency injection — rewrite service factory."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.kb.relationship_repository import RelationshipRepository
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.rewrite_service import RewriteService


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
    from narrare.writing.deps_pipeline import create_pipeline
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.rewrite_service import RewriteService
    from narrare_core.writing.draft_processor import DraftProcessor

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

    draft_processor = DraftProcessor()
    pipeline = create_pipeline(draft_processor)
    repo = GenerationRepository(session)
    relationship_repo = RelationshipRepository(session)
    tone_service = CustomToneService(repo=UserSettingsRepository(session))

    return RewriteService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        tone_service=tone_service,
        relationship_repo=relationship_repo,
    )
