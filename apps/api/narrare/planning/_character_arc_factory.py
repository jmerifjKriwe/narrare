"""Service factory for character arc — wires CharacterArcService with model routing.

Follows the same pattern as ``_service_factory.py``: resolves the user's
configured provider/model for the PLAN intent, validates novel existence,
and builds the service with proper DI.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare._app.dependencies import get_model_registry, get_model_routing_resolver
from narrare.novels.repository import NovelRepository
from narrare.planning.character_arc_service import CharacterArcService
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def get_character_arc_service(
    session: AsyncSession,
    user_id: str,
    novel_id: uuid.UUID,
) -> CharacterArcService:
    """Wire up CharacterArcService with model routing from user settings.

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
        Fully wired CharacterArcService.

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

    return CharacterArcService(
        novel_repo=novel_repo,
        model_registry=registry,
        model_config=model_config,
        api_key=api_key,
        base_url=base_url,
    )
