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
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
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
    """Factory for ChapterSummaryService — lazily wires the SUMMARIZE cascades.

    Both cascades are wired LAZILY (ADR-086 L38, ``deps_style_variants.py``
    L35 precedent): the factory builds a ``LazyModelResolution`` around the
    per-user routing cascade (``resolver.resolve(LLMIntent.SUMMARIZE,
    user_id, novel_id)``) and a deferred runtime composition awaiting BOTH
    cascades — routing plus token limits (RULE-18/18b: sources unchanged,
    only timing moves) — then assembling the effective config
    (``temperature=0.3``, ``max_tokens=limits.output_limit``). No
    resolution happens at construction: FastAPI solves all
    sub-dependencies BEFORE body validation, so an eager cascade here
    would preempt legitimate 422s with a 400 ``NO_AI_PROVIDER``. The
    composition runs once at the service's first use
    (``ChapterSummaryService.ensure_resolved``, after the ownership gate);
    ``ConfigurationError`` propagates loudly from the entry point
    (RULE-11 — REST, no SSE pre-header needed).

    Args:
        user_id: The authenticated user's ID (from auth dependency).
        novel_id: Optional novel ID for project-level model overrides.
        session: Async database session (from session dependency).

    Returns:
        A configured ChapterSummaryService instance.
    """
    from narrare._app.config import get_settings
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing._summary_invocation import SummaryModelRuntime
    from narrare.writing.summary_service import ChapterSummaryService

    resolver = get_model_routing_resolver(session)
    user_uuid = UUID(user_id)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.SUMMARIZE, user_uuid, novel_id)
    )

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )

    async def compose_runtime() -> SummaryModelRuntime:
        """Resolve both cascades and assemble the runtime at first use.

        Awaits the (cached) SUMMARIZE routing resolution and the
        token-limits cascade, then freezes the effective config — the
        eager factory's verbatim sampling overlay (``temperature=0.3``,
        ``max_tokens=limits.output_limit``) — plus the routing cascade's
        per-user credentials.
        """
        resolved = await model_resolution.resolve()
        limits = await token_limits_service.get_resolved_limits(
            user_id=user_id,
            project_id=str(novel_id) if novel_id else None,
        )
        config = replace(
            resolved.config,
            temperature=0.3,
            max_tokens=limits.output_limit,
        )
        return SummaryModelRuntime(
            config=config,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )

    registry = get_model_registry()
    repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    composer = get_composer()

    # Canonical KB-context provider (ADR-067): single fetch+render source for
    # the kb_characters / kb_locations / kb_factions / kb_relationships
    # prompt variables. Degrades gracefully (RULE-11). Active since the
    # summarize template's header-demotion activation slice: the
    # Knowledge-Base region renders (no longer below the parse cutoff);
    # degradation → empty bundle (RULE-11).
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository

    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    return ChapterSummaryService(
        registry=registry,
        runtime_factory=compose_runtime,
        chapter_repo=repo,
        novel_repo=novel_repo,
        composer=composer,
        invocation_pipeline=get_invocation_pipeline(),
        kb_context_provider=kb_context_provider,
    )
