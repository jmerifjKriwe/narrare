"""Analysis dependency injection factory — beta reader (RULE-04 split).

Extracted from ``dependencies.py`` to keep that file under the 200-line
dependency-file limit (RULE-04). Production wiring for ``BetaReaderService``
lives here.

Model acquisition follows the per-user model-routing cascade with LAZY
first-use resolution (ADR-086): the factory wires a ``LazyModelResolution``
around ``resolver.resolve(LLMIntent.BETA_READ, user_id, novel_id)`` and a
deferred budget-assembler composition — no resolution at construction
(FastAPI solves all sub-dependencies BEFORE body validation, so an eager
resolve here would preempt legitimate 422s with 404/400/500s). Both the
routing cascade and the token-limits cascade (RULE-18b — source
unchanged, only timing moves) run at the service's first use, inside the
service layer. ``ConfigurationError`` propagates loudly at first use
(RULE-11; analysis routers are auth-mandatory). No business logic lives
here — only wiring.

See:
    ADR-067 — Reusable KB-Context Provider (KB context routing)
    ADR-082 — Context budgets (resolved against the user's model window)
    ADR-086 — Lazy model resolution (timing-only deferral)
    CONSTRAINTS.md RULE-04/06/07/11/18b
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import (  # noqa: TC001 — needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.analysis.beta_reader_service import BetaReaderService
    from narrare_core.analysis.assembler import AnalysisContextAssembler


async def get_beta_reader_service(
    session: SessionDep,
    user_id: CurrentUserIdDep,
    novel_id: uuid.UUID,
) -> BetaReaderService:
    """Create a BetaReaderService with lazily-wired per-user routing.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - ChapterRepository + NovelRepository for context
    - Canonical KBContextProvider (ADR-067) for kb_characters / kb_locations,
      rendered through the ADR-050 envelope with provenance (FIND-017).
    - InMemorySessionCache for result caching (30min TTL)
    - InvocationPipeline for invocation evidence (ADR-040)
    - A deferred budget-assembler composition (ADR-082/ADR-086): the
      AnalysisContextAssembler is built at first use from the resolved
      ``context_total_budget`` (cascade-resolved, capped by the analysis
      model's window; series_in_scope=False per Decision 5).

    FastAPI resolves ``novel_id`` from the endpoints' declared
    ``novel_id`` parameter (query) and ``user_id`` via
    ``CurrentUserIdDep`` (both beta-reader endpoints declare them).
    The model routing and token limits resolve through their cascades
    at the service's FIRST USE — NOT here (ADR-086): construction
    happens pre-body-validation, and eager resolution would preempt
    422s (and the P2 novel guard would preempt them with 404s).
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
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

    resolver = get_model_routing_resolver(session)
    user_uuid = uuid.UUID(user_id)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.BETA_READ, user_uuid, novel_id)
    )

    registry = get_model_registry()
    composer = get_composer()
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

    # ADR-082 + ADR-086: the analysis input-context total resolves through
    # the token-limits cascade against the analysis model's window.
    # Analysis has no series-history tier -> series_in_scope=False (full
    # total; Decision 5). DEFERRED: composed at the service's first use
    # (post-body-validation) together with the routing cascade it depends
    # on — RULE-18b: sources unchanged, only timing moves.
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )

    async def compose_budget_assembler() -> AnalysisContextAssembler:
        """Compose the model-capped budget assembler at first use.

        Awaits the (cached) routing resolution and the token-limits
        cascade, then builds the assembler at the resolved
        ``context_total_budget`` (ADR-082 Decision 5).
        """
        resolved = await model_resolution.resolve()
        limits = await token_limits_service.get_resolved_limits(
            user_id=user_id,
            project_id=str(novel_id),
        )
        budgets = resolve_context_budgets(
            limits=limits,
            config=resolved.config,
            series_in_scope=False,
        )
        return AnalysisContextAssembler(total_budget=budgets.context_total)

    # In-memory cache with 30min TTL (ADR-080)
    cache = InMemorySessionCache()
    beta_cache = BetaReaderCache(cache)

    return BetaReaderService(
        context_assembler=assembler,
        cache=beta_cache,
        registry=registry,
        model_resolution=model_resolution,
        composer=composer,
        budget_assembler_factory=compose_budget_assembler,
        invocation_pipeline=invocation_pipeline,
    )
