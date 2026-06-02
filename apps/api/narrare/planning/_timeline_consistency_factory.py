"""Service factory for timeline consistency — wires TimelineConsistencyService.

Follows the same pattern as ``_timeline_analysis_factory.py``: resolves the
user's configured provider/model for the PLAN intent, validates novel existence,
and builds the consistency service with proper DI.

Phase 3 adds CharacterAgeService wiring for character age integration.
LLM checks are optional — the service gracefully degrades when no AI provider
is configured (deterministic-only mode).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare._app.dependencies import get_model_registry, get_model_routing_resolver
from narrare.kb.repository import KBRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.character_age_service import CharacterAgeService
from narrare.planning.timeline_consistency_service import TimelineConsistencyService
from narrare.planning.timeline_repository import TimelineEventRepository
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def get_timeline_consistency_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> TimelineConsistencyService:
    """Wire up TimelineConsistencyService with model routing from user settings.

    Resolves the user's configured provider/model for the PLAN intent,
    validates novel existence before calling the resolver to prevent
    auto-creation of project_settings for nonexistent novels.

    Gracefully degrades when no AI provider is configured — the service
    will run deterministic checks only.

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired TimelineConsistencyService.

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

    # Wire CharacterAgeService for KB character metadata reads.
    character_age_service = CharacterAgeService(
        novel_repo=novel_repo,
        kb_repo=KBRepository(session),
    )

    return TimelineConsistencyService(
        event_repo=TimelineEventRepository(session),
        novel_repo=novel_repo,
        character_age_service=character_age_service,
        model_registry=registry,
        model_config=model_config,
    )
