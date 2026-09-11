"""Summary module dependency injection — factories and resolvers.

All dependencies are injected via __init__ (DI pattern).
No business logic lives here — only wiring.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.database import get_async_session
from narrare._app.dependencies import (
    get_composer,
    get_current_user_id,
    get_invocation_pipeline,
    get_model_registry,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.summary_service import ChapterSummaryService


async def get_summary_service(
    user_id: str = Depends(get_current_user_id),
    novel_id: UUID | None = None,
    session: AsyncSession = Depends(get_async_session),  # noqa: B008
) -> ChapterSummaryService:
    """Factory for ChapterSummaryService — resolves model config per user.

    FastAPI dependency: session and user_id are resolved via Depends.
    novel_id is extracted from request query parameters.

    Args:
        user_id: The authenticated user's ID (from auth dependency).
        novel_id: Optional novel ID for project-level model overrides.
        session: Async database session (from session dependency).

    Returns:
        A configured ChapterSummaryService instance.
    """
    from narrare.writing.summary_service import ChapterSummaryService

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.SUMMARIZE,
        UUID(user_id),
        novel_id,
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
        project_id=str(novel_id) if novel_id else None,
    )
    config = replace(
        resolved.config,
        temperature=0.3,
        max_tokens=limits.output_limit,
    )

    registry = get_model_registry()
    repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    composer = get_composer()

    return ChapterSummaryService(
        registry=registry,
        config=config,
        chapter_repo=repo,
        novel_repo=novel_repo,
        composer=composer,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        invocation_pipeline=get_invocation_pipeline(),
    )
