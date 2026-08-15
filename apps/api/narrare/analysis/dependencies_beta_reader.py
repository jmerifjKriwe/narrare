"""Analysis dependency injection factory — beta reader (RULE-04 split).

Extracted from ``dependencies.py`` to keep that file under the 200-line
dependency-file limit (RULE-04). Production wiring for ``BetaReaderService``
lives here.

See:
    ADR-067 — Reusable KB-Context Provider (KB context routing)
    CONSTRAINTS.md RULE-04/06/07/11
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for FastAPI DI
from typing import TYPE_CHECKING

from narrare._app.dependencies import (  # noqa: TC001 — needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)

if TYPE_CHECKING:
    from narrare.analysis.beta_reader_service import BetaReaderService


async def get_beta_reader_service(
    session: SessionDep,
    user_id: CurrentUserIdDep,
    novel_id: uuid.UUID,
) -> BetaReaderService:
    """Create a BetaReaderService with injected dependencies.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - ChapterRepository + NovelRepository for context
    - Canonical KBContextProvider (ADR-067) for kb_characters / kb_locations,
      rendered through the ADR-050 envelope with provenance (FIND-017).
    - InMemorySessionCache for result caching (30min TTL)
    - InvocationPipeline for invocation evidence (ADR-040)
    - AnalysisContextAssembler at the resolved, model-capped
      context_total_budget (ADR-082 Decision 5 — analysis joins
      context_total_budget, capped by the analysis model's window).

    FastAPI resolves ``novel_id`` from the endpoints' declared
    ``novel_id`` parameter (query) and ``user_id`` via
    ``CurrentUserIdDep`` (both beta-reader endpoints declare them).
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.analysis.beta_reader_cache import BetaReaderCache
    from narrare.analysis.beta_reader_service import BetaReaderService
    from narrare.analysis.context_assembler import ContextAssembler
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.settings.token_limits.context_budgets import resolve_context_budgets
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService
    from narrare_core.analysis.assembler import AnalysisContextAssembler
    from narrare_core.cache import InMemorySessionCache

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)
    invocation_pipeline = get_invocation_pipeline()

    # Repositories
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    # Canonical KB-context provider (ADR-067): single fetch+render source for
    # the beta-reader's kb_characters / kb_locations slots, rendered through
    # the ADR-050 envelope with provenance annotated (FIND-017). Degrades
    # gracefully (RULE-11).
    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    # Context assembler
    assembler = ContextAssembler(
        chapter_repo=chapter_repo,
        kb_context_provider=kb_context_provider,
        novel_repo=novel_repo,
    )

    # ADR-082: resolve the analysis input-context total through the cascade
    # and against the analysis model's window. Analysis has no series-history
    # tier -> series_in_scope=False (full total; Decision 5).
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(novel_id),
    )
    budgets = resolve_context_budgets(
        limits=limits,
        config=config,
        series_in_scope=False,
    )

    # In-memory cache with 30min TTL (ADR-080)
    cache = InMemorySessionCache()
    beta_cache = BetaReaderCache(cache)

    return BetaReaderService(
        context_assembler=assembler,
        cache=beta_cache,
        registry=registry,
        config=config,
        composer=composer,
        budget_assembler=AnalysisContextAssembler(total_budget=budgets.context_total),
        invocation_pipeline=invocation_pipeline,
    )
