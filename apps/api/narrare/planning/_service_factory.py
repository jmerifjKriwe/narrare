"""Service factory for planning router — wires StoryboardService with model routing.

Extracted from router.py to respect the 150-line file size limit (RULE-04).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare._app.dependencies import get_model_registry
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.repository import OutlineRepository
from narrare.planning.service import StoryboardService
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def get_storyboard_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> StoryboardService:
    """Wire up StoryboardService with model routing from user settings.

    Resolves the user's configured provider/model for the PLAN intent
    so that AI-powered remap can use the LLM gateway (RULE-01b).

    Validates novel existence BEFORE calling the resolver to prevent
    auto-creation of project_settings for a nonexistent novel (FK
    constraint violation). Gracefully degrades when no AI provider is
    configured — storyboard, outlines, and sync work without AI.
    """
    from narrare_core.llm.intents import LLMIntent

    uid = uuid.UUID(user_id)

    # Validate novel exists BEFORE resolver auto-creates project_settings.
    novel_repo = NovelRepository(session)
    novel = await novel_repo.get_by_id(novel_id, uid)
    if novel is None:
        raise NotFoundError("Novel", identifier=str(novel_id))

    # Resolve model config — gracefully handle missing AI provider.
    registry = get_model_registry()
    model_config = None
    api_key = None
    base_url = None
    try:
        resolver = get_model_routing_resolver(session)
        resolved = await resolver.resolve(LLMIntent.PLAN, uid, novel_id)
        model_config = resolved.config
        api_key = resolved.api_key
        base_url = resolved.base_url
    except ConfigurationError:
        logger.info("no_ai_provider_configured", novel_id=str(novel_id))

    return StoryboardService(
        outline_repo=OutlineRepository(session),
        chapter_repo=ChapterRepository(session),
        novel_repo=novel_repo,
        model_registry=registry,
        model_config=model_config,
        api_key=api_key,
        base_url=base_url,
    )
