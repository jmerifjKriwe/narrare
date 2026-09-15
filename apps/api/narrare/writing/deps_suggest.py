"""Writing module dependency injection — suggest service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies import get_composer, get_model_registry
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare.writing.deps_ownership import ensure_novel_owned
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.suggest_service import InlineSuggestService


async def get_suggest_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> InlineSuggestService:
    """Factory for InlineSuggestService — lazily wires the SUGGEST cascade.

    The per-user model-routing cascade
    (``resolver.resolve(LLMIntent.SUGGEST, user_id, project_id)``) is
    wired as a ``LazyModelResolution`` and resolves on the service's
    first use (ADR-086) — never at construction. The service composes
    the suggest sampling overrides (temperature 0.3, SUGGEST_MAX_TOKENS)
    at that same first use, exactly as this factory previously did
    eagerly (timing-only migration — WHAT unchanged, only WHEN).

    Raises:
        NotFoundError: If ``project_id`` is given but unknown or not
            owned by ``user_id`` (fix-wave N1, consistency close: gated
            BEFORE the resolver's auto-creating project-settings read —
            foreign ≡ unknown → 404, never a 500 FK oracle). The only
            production caller passes ``project_id=None`` (user scope;
            the gate passes without a query); the gate protects any
            future project-scoped wiring.
    """
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.writing.suggest_service import InlineSuggestService

    # Fix-wave N1: gate the project scope BEFORE model routing — the
    # resolver's project-settings read auto-creates a row (unknown novel
    # → FK IntegrityError = 500 oracle; foreign novel → victim row).
    await ensure_novel_owned(session, user_id, project_id)

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.SUGGEST, UUID(user_id), project_id)
    )

    registry = get_model_registry()
    composer = get_composer()
    chapter_repo = ChapterRepository(session)
    # IDOR S6: novel repo backs the chapter-ownership gate.
    novel_repo = NovelRepository(session)

    return InlineSuggestService(
        registry=registry,
        composer=composer,
        model_resolution=model_resolution,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )
