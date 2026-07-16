"""Service factory for timeline analysis — wires TimelineAnalysisService.

Follows the same pattern as ``_timeline_factory.py``: resolves the user's
configured provider/model for the PLAN intent, validates novel existence,
and builds the analysis service with proper DI.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare._app.dependencies import get_composer, get_invocation_pipeline, get_model_registry
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.planning.timeline_analysis_service import TimelineAnalysisService
from narrare.planning.timeline_repository import TimelineEventRepository
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def get_timeline_analysis_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> TimelineAnalysisService:
    """Wire up TimelineAnalysisService with model routing from user settings.

    Resolves the user's configured provider/model for the PLAN intent,
    validates novel existence before calling the resolver to prevent
    auto-creation of project_settings for nonexistent novels.

    Gracefully degrades when no AI provider is configured — the service
    will use the fallback model from ModelRegistry.

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired TimelineAnalysisService.

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
    # PromptComposer for governed timeline system-prompt resolution
    # (RULE-02 / ADR-049 D9). Same source as the KB consistency factory.
    composer = get_composer()
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

    # Canonical KB-context provider (ADR-067): supplies kb_characters/
    # kb_locations/kb_factions/kb_relationships, rendered through the ADR-050
    # envelope with provenance (FIND-017). Degrades gracefully (RULE-11).
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository

    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    return TimelineAnalysisService(
        novel_repo=novel_repo,
        chapter_repo=ChapterRepository(session),
        model_registry=registry,
        model_config=model_config,
        composer=composer,
        event_repo=TimelineEventRepository(session),
        kb_context_provider=kb_context_provider,
        api_key=api_key,
        base_url=base_url,
        invocation_pipeline=get_invocation_pipeline(),
    )
