"""Writing module dependency injection — suggest service factory."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies import get_composer, get_model_registry
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import SUGGEST_MAX_TOKENS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.suggest_service import InlineSuggestService


async def get_suggest_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> InlineSuggestService:
    """Factory for InlineSuggestService — resolves model config for SUGGEST."""
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.writing.suggest_service import InlineSuggestService

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        LLMIntent.SUGGEST,
        UUID(user_id),
        project_id,
    )
    config = replace(resolved.config, temperature=0.3, max_tokens=SUGGEST_MAX_TOKENS)

    registry = get_model_registry()
    composer = get_composer()
    chapter_repo = ChapterRepository(session)
    # IDOR S6: novel repo backs the chapter-ownership gate.
    novel_repo = NovelRepository(session)

    return InlineSuggestService(
        registry=registry,
        composer=composer,
        config=config,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
