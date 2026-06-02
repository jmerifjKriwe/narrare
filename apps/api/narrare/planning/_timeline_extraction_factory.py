"""Service factory for timeline extraction — wires TimelineExtractionService.

Follows the same pattern as ``_timeline_analysis_factory.py``: resolves
the user's configured provider/model for the PLAN intent, validates novel
existence, and builds the extraction service with proper DI.

Extraction is split from analysis to keep file sizes under the 300-line
limit (RULE-04).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare._app.dependencies import get_model_registry, get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.timeline_extraction_service import TimelineExtractionService
from narrare.planning.timeline_repository import TimelineEventRepository
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def get_timeline_extraction_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> TimelineExtractionService:
    """Wire up TimelineExtractionService with model routing from user settings.

    Resolves the user's configured provider/model for the PLAN intent,
    validates novel existence before calling the resolver to prevent
    auto-creation of project_settings for nonexistent novels.

    Gracefully degrades when no AI provider is configured — the service
    will raise ConfigurationError when extraction is attempted.

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired TimelineExtractionService.

    Raises:
        NotFoundError: If the novel does not exist.
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
    try:
        resolver = get_model_routing_resolver(session)
        resolved = await resolver.resolve(LLMIntent.PLAN, uid, novel_id)
        model_config = resolved.config
    except ConfigurationError:
        logger.info("no_ai_provider_configured", novel_id=str(novel_id))

    return TimelineExtractionService(
        novel_repo=novel_repo,
        chapter_repo=ChapterRepository(session),
        model_registry=registry,
        model_config=model_config,
        event_repo=TimelineEventRepository(session),
    )
