"""Writing module dependency injection — writing service factory.

The :func:`get_session_memory_instance` singleton that backs
``get_writing_service`` lives in :mod:`narrare.writing._session_memory_deps`
(extracted per RULE-04). The singleton hosts its own module-level
``is_mem0_available`` / ``detect_provider_from_env`` imports so the
autouse ``_no_real_mem0_clients`` test guard can patch the re-imported
reference — see ADR-068 for the full rationale.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.kb.relationship_repository import RelationshipRepository
from narrare.writing._session_memory_deps import get_session_memory_instance
from narrare.writing.deps_ownership import ensure_novel_owned
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import SUGGEST_MAX_TOKENS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.writing.service import WritingService

logger = structlog.get_logger(__name__)


async def get_writing_service(
    session: AsyncSession,
    user_id: str,
    project_id: UUID | None = None,
    intent: LLMIntent = LLMIntent.WRITE,
) -> WritingService:
    """Factory for WritingService — resolves model config per user/intent.

    Args:
        session: DB session for repository and settings lookups.
        user_id: Authenticated user identifier.
        project_id: Optional project/novel ID for project-level settings.
        intent: LLM operation intent.  Controls model routing and prompt
            selection.  Defaults to ``LLMIntent.WRITE`` (full chapter).
            Use ``LLMIntent.SUGGEST`` for lightweight inline suggestions.

    Returns:
        Configured WritingService ready for use.

    Raises:
        NotFoundError: If ``project_id`` is given but unknown or not
            owned by ``user_id`` (fix-wave N1: gated BEFORE the
            auto-creating project-settings reads of the resolver and
            token-limit service — foreign ≡ unknown → 404, never a
            500 FK oracle).
    """
    from narrare._app.config import get_settings
    from narrare.chapters.repository import ChapterRepository
    from narrare.settings.custom_tone_service import CustomToneService
    from narrare.settings.model_routing_resolver import ModelRoutingResolverImpl
    from narrare.settings.repository import UserSettingsRepository
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare.writing.deps_pipeline import create_pipeline
    from narrare.writing.repository import GenerationRepository
    from narrare.writing.service import WritingService
    from narrare_core.writing.draft_processor import DraftProcessor

    # Fix-wave N1: gate the project scope BEFORE model routing / token
    # limits — both read project-keyed settings through auto-creating
    # repositories (unknown novel → FK IntegrityError = 500 oracle;
    # foreign novel → transient victim row).
    await ensure_novel_owned(session, user_id, project_id)

    resolver = get_model_routing_resolver(session)
    assert isinstance(resolver, ModelRoutingResolverImpl)
    resolved = await resolver.resolve(
        intent,
        UUID(user_id),
        project_id,
    )
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(project_id) if project_id else None,
    )
    # ADR-082: resolve input-context budgets against the writing model's
    # window. Series membership decides the guarded carve-out (Decision 6):
    # series novels allocate tiers over total - series_history; standalones
    # over the full total.
    from narrare.novels.repository import NovelRepository

    # IDOR S6: novel repo backs the verify_chapter_access ownership gate
    # inside start_generation (via _helpers.start_generation_request) and
    # the series-in-scope resolution below.
    novel_repo = NovelRepository(session)
    series_in_scope = False
    if project_id is not None:
        novel = await novel_repo.get(project_id)
        series_in_scope = novel is not None and novel.series_id is not None

    budgets = resolve_context_budgets(
        limits=limits,
        config=resolved.config,
        series_in_scope=series_in_scope,
    )
    config = replace(
        resolved.config,
        temperature=0.7,
        max_tokens=limits.output_limit,
    )
    if intent == LLMIntent.SUGGEST:
        # SUGGEST uses a fixed 60-token limit — inline suggestions must be short
        # (UX constraint, not a profile concern).
        config = replace(config, temperature=0.3, max_tokens=SUGGEST_MAX_TOKENS)

    draft_processor = DraftProcessor()
    pipeline = create_pipeline(
        draft_processor,
        tier_overrides=limits.tier_percentages,
        total_budget=budgets.writing_tier_base,
    )
    repo = GenerationRepository(session)
    relationship_repo = RelationshipRepository(session)
    tone_service = CustomToneService(repo=UserSettingsRepository(session))
    session_memory = get_session_memory_instance()

    # Spec 2 / SERIES-002: series-history context provider. Pre-fetches prior
    # bands' BandSummary data and assembles ``{{series_history}}``. Returns ""
    # for standalone novels (RULE-11 graceful), so wiring it here is safe for
    # non-series writing.
    from narrare.series.band_summary_repository import BandSummaryRepository
    from narrare.series.repository import SeriesRepository
    from narrare.series.series_history_provider import SeriesHistoryProvider

    series_history_provider = SeriesHistoryProvider(
        novel_repo=novel_repo,
        series_repo=SeriesRepository(session),
        band_summary_repo=BandSummaryRepository(session),
    )

    return WritingService(
        repo=repo,
        pipeline=pipeline,
        draft_processor=draft_processor,
        config=config,
        chapter_repo=ChapterRepository(session),
        novel_repo=novel_repo,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        tone_service=tone_service,
        relationship_repo=relationship_repo,
        session_memory=session_memory,
        series_history_provider=series_history_provider,
        series_history_budget=budgets.series_history,
    )
