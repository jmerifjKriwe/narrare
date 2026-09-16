"""Writing module dependency injection — coauthor service factories."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare.kb.relationship_repository import RelationshipRepository
from narrare.writing.deps_ownership import ensure_novel_owned
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing._coauthor_support import CoAuthorRuntime
    from narrare.writing.coauthor_apply_service import CoAuthorApplyService
    from narrare.writing.coauthor_service import CoAuthorService


async def get_coauthor_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
) -> CoAuthorService:
    """Factory for CoAuthorService — lazily wires the CO_AUTHOR cascades.

    Both cascades are wired LAZILY (ADR-086, M-budget /
    ``dependencies_beta_reader.py`` S4b precedent): the factory builds a
    ``LazyModelResolution`` around the per-user routing cascade
    (``resolver.resolve(LLMIntent.CO_AUTHOR, user_id, project_id)``) and a
    deferred runtime composition awaiting BOTH cascades — routing plus
    token limits (RULE-18/18b: sources unchanged, only timing moves) —
    then assembling the effective config (``temperature=0.7``,
    ``max_tokens=limits.output_limit``), the ADR-082 budgets
    (``series_in_scope=False``, Decision 6 standalone semantics), the
    tier-wired pipeline, and the SET-005 ``max_selection_words`` limit.
    No resolution happens at construction: FastAPI solves all
    sub-dependencies BEFORE body validation, so an eager cascade here
    would preempt legitimate 422s with a 400 ``NO_AI_PROVIDER``. The
    composition runs once at the service's first use
    (``CoAuthorService.ensure_resolved``, after the ownership gate);
    ``ConfigurationError`` propagates loudly from the entry point
    (RULE-11 — auth-mandatory SSE router).

    Raises:
        NotFoundError: If ``project_id`` is given but unknown or not
            owned by ``user_id`` (fix-wave N1: gated BEFORE the
            auto-creating project-settings reads of the resolver and
            token-limit service — foreign ≡ unknown → 404, never a
            500 FK oracle).
    """
    from narrare._app.config import get_settings
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing._coauthor_support import CoAuthorRuntime
    from narrare.writing.coauthor_service import CoAuthorService
    from narrare.writing.deps_pipeline import create_pipeline
    from narrare.writing.repository import GenerationRepository
    from narrare_core.writing.draft_processor import DraftProcessor

    # Fix-wave N1: gate the project scope BEFORE model routing / token
    # limits — both read project-keyed settings through auto-creating
    # repositories (unknown novel → FK IntegrityError = 500 oracle;
    # foreign novel → transient victim row).
    await ensure_novel_owned(session, user_id, project_id)

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    user_uuid = UUID(user_id)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.CO_AUTHOR, user_uuid, project_id)
    )

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    draft_processor = DraftProcessor()

    async def compose_runtime() -> CoAuthorRuntime:
        """Resolve both cascades and assemble the runtime at first use.

        Awaits the (cached) CO_AUTHOR routing resolution and the
        token-limits cascade, then freezes the effective config, the
        tier-wired pipeline (ADR-082: tiers allocate over the full
        effective total — this path never injects ``{{series_history}}``),
        and the SET-005 selection-word limit.
        """
        resolved = await model_resolution.resolve()
        limits = await token_limits_service.get_resolved_limits(
            user_id=user_id,
            project_id=str(project_id) if project_id else None,
        )
        config = replace(
            resolved.config,
            temperature=0.7,
            max_tokens=limits.output_limit,
        )
        budgets = resolve_context_budgets(
            limits=limits,
            config=resolved.config,
            series_in_scope=False,
        )
        pipeline = create_pipeline(
            draft_processor,
            tier_overrides=limits.tier_percentages,
            total_budget=budgets.writing_tier_base,
        )
        return CoAuthorRuntime(
            config=config,
            api_key=resolved.api_key,
            base_url=resolved.base_url,
            pipeline=pipeline,
            max_selection_words=limits.max_selection_words,
        )

    repo = GenerationRepository(session)
    relationship_repo = RelationshipRepository(session)
    # IDOR S6: chapter/novel repos back the verify_chapter_access gate.
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    return CoAuthorService(
        repo=repo,
        runtime_factory=compose_runtime,
        draft_processor=draft_processor,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        relationship_repo=relationship_repo,
    )


async def get_coauthor_apply_service(
    session: AsyncSession,
) -> CoAuthorApplyService:
    """Lightweight factory — repos only, no pipeline or model config."""
    from narrare.chapters.repository import ChapterRepository
    from narrare.writing.coauthor_apply_service import CoAuthorApplyService
    from narrare.writing.repository import GenerationRepository

    return CoAuthorApplyService(
        repo=GenerationRepository(session),
        chapter_repo=ChapterRepository(session),
    )
