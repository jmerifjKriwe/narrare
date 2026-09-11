"""Consistency dependency injection factories.

Updated for ADR-044: injects ``ConsistencyOrchestrator`` for the staged
pipeline. When the orchestrator is present, the service uses the two-stage
flow (FactExtractor → ConsistencyAgent). Otherwise falls back to legacy.

Model acquisition follows the per-user model-routing cascade: the factory
resolves TWO configs for the authenticated user (+ novel for project-level
overrides) — ``LLMIntent.FACT_EXTRACT`` for the ADR-044 stage-1 fact
extractor (feature ``consistency_fact_extraction``) and
``LLMIntent.CONSISTENCY`` for the checker (staged stage 2 and the legacy
single-pass fallback) — and passes the resolved configs + credentials into
the orchestrator and service that own the actual ``get_model`` calls. The
legacy temperature overrides (0.2 extractor / 0.3 checker) are preserved
via ``dataclasses.replace`` on the RESOLVED cascade configs, so the
cascade's model/provider routing stays untouched. No business logic lives
here — only wiring.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import (  # noqa: TC001 — needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.consistency.ref_index import CrossFeatureRefIndexImpl


async def get_consistency_service(
    session: SessionDep,
    user_id: CurrentUserIdDep,
    novel_id: uuid.UUID,
) -> ConsistencyCheckerService:
    """Create a ConsistencyCheckerService with per-user resolved model routing.

    Production wiring:
    - ModelRoutingResolver for the per-user model cascade (FACT_EXTRACT +
      CONSISTENCY intents); ``ConfigurationError`` propagates when the
      user has no provider configured (consistency routers are
      auth-mandatory).
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - ConsistencyOrchestrator for staged pipeline (ADR-044), carrying the
      resolved credentials for both stages
    - Repositories for data access
    - TokenLimitsService for dynamic context cap resolution

    FastAPI resolves ``novel_id`` from the endpoints' declared
    ``novel_id`` parameter, ``user_id`` via ``CurrentUserIdDep``, and the
    session via ``SessionDep``.
    """
    from dataclasses import replace

    from narrare._app.config import get_settings
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    resolver = get_model_routing_resolver(session)
    fact_resolved = await resolver.resolve(
        LLMIntent.FACT_EXTRACT,
        uuid.UUID(user_id),
        novel_id,
    )
    consistency_resolved = await resolver.resolve(
        LLMIntent.CONSISTENCY,
        uuid.UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()
    composer = get_composer()
    invocation_pipeline = get_invocation_pipeline()

    # Legacy temperature overrides preserved on the RESOLVED cascade
    # configs (dataclasses.replace — model/provider routing stays intact).
    consistency_config = replace(consistency_resolved.config, temperature=0.3)

    # Fact extractor config for staged pipeline (ADR-044)
    fact_extractor_config = replace(fact_resolved.config, temperature=0.2)

    # Repositories
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)
    timeline_repo = TimelineEventRepository(session)
    relationship_repo = RelationshipRepository(session)

    # Orchestrator for staged pipeline — carries the resolved user
    # credentials for BOTH stages (extractor + checker).
    orchestrator = ConsistencyOrchestrator(
        registry=registry,
        fact_extractor_config=fact_extractor_config,
        consistency_config=consistency_config,
        composer=composer,
        invocation_pipeline=invocation_pipeline,
        fact_extractor_api_key=fact_resolved.api_key,
        fact_extractor_base_url=fact_resolved.base_url,
        consistency_api_key=consistency_resolved.api_key,
        consistency_base_url=consistency_resolved.base_url,
    )

    # TokenLimitsService for dynamic context caps
    settings = get_settings()
    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=settings,
    )

    return ConsistencyCheckerService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        kb_repo=kb_repo,
        timeline_repo=timeline_repo,
        relationship_repo=relationship_repo,
        registry=registry,
        config=consistency_config,
        composer=composer,
        token_limits_service=token_limits_service,
        orchestrator=orchestrator,
        invocation_pipeline=invocation_pipeline,
        api_key=consistency_resolved.api_key,
        base_url=consistency_resolved.base_url,
    )


def get_cross_feature_ref_index(session: SessionDep) -> CrossFeatureRefIndexImpl:
    """Create the read-side ADR-050 cross-feature ref index."""
    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.ref_index import CrossFeatureRefIndexImpl
    from narrare.kb.repository import KBRepository
    from narrare.planning.repository import OutlineRepository
    from narrare.planning.timeline_repository import TimelineEventRepository

    return CrossFeatureRefIndexImpl(
        kb_repo=KBRepository(session),
        timeline_repo=TimelineEventRepository(session),
        outline_repo=OutlineRepository(session),
        chapter_repo=ChapterRepository(session),
    )
