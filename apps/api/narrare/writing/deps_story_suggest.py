"""Service factory for story suggest — wires StorySuggestService with model routing.

Follows the same pattern as ``planning/_character_arc_factory.py``: resolves
the user's configured provider/model for the SUGGEST intent, validates novel
existence, and builds the service with proper DI.

See WRITE-009 (Writer's Unblock Tools).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare._app.dependencies import (
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.novels.repository import NovelRepository
from narrare.planning.repository import OutlineRepository
from narrare.writing.story_suggest_service import StorySuggestService
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def get_story_suggest_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> StorySuggestService:
    """Wire up StorySuggestService with model routing from user settings.

    Resolves the user's configured provider/model for the SUGGEST intent,
    validates novel existence before calling the resolver to prevent
    auto-creation of project_settings for nonexistent novels.

    Gracefully degrades when no AI provider is configured — the service
    will use the fallback model from ModelRegistry.

    Pre-validates novel existence so :class:`NotFoundError` fires during
    dependency resolution (before SSE headers are sent), avoiding the
    RuntimeError that occurs when validation errors fire after headers.

    Args:
        session: DB session.
        user_id: Current user ID (string, will be parsed to UUID).
        novel_id: Target novel UUID.

    Returns:
        Fully wired StorySuggestService.

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
    composer = get_composer()
    model_config = None
    try:
        resolver = get_model_routing_resolver(session)
        resolved = await resolver.resolve(LLMIntent.SUGGEST, uid, novel_id)
        model_config = resolved.config
    except ConfigurationError:
        logger.info("no_ai_provider_configured", novel_id=str(novel_id))

    return StorySuggestService(
        novel_repo=novel_repo,
        model_registry=registry,
        model_config=model_config,
        composer=composer,
        outline_repo=OutlineRepository(session),
        invocation_pipeline=get_invocation_pipeline(),
    )
