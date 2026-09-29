"""Consistency dependency injection factories.

Updated for ADR-044: injects ``ConsistencyOrchestrator`` for the staged
pipeline. When the orchestrator is present, the service uses the two-stage
flow (FactExtractor → ConsistencyAgent). Otherwise falls back to legacy.

Model acquisition follows the per-user model-routing cascade with LAZY
first-use resolution (ADR-086 L13, S4b-dual shape): the factory wires
TWO ``LazyModelResolution``s for the authenticated user (+ novel for
project-level overrides) — ``LLMIntent.FACT_EXTRACT`` for the ADR-044
stage-1 fact extractor (feature ``consistency_fact_extraction``) and
``LLMIntent.CONSISTENCY`` for the checker (staged stage 2 and the
legacy single-pass fallback). Neither cascade runs at construction —
FastAPI solves all sub-dependencies BEFORE body validation, so an eager
resolve here would preempt legitimate 422s. Both cascades resolve at
the service's first use (``ensure_resolved``), where the legacy
temperature overrides (0.2 extractor / 0.3 checker) are composed onto
the RESOLVED cascade configs via ``dataclasses.replace`` — the
cascade's model/provider routing stays untouched. The orchestrator and
service own the actual ``get_model``/``prepare`` calls. No business
logic lives here — only wiring.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare._app.dependencies import (  # noqa: TC001 — needed at runtime for FastAPI DI
    CurrentUserIdDep,
    SessionDep,
)
from narrare._app.dependencies_services import LazyModelResolution, get_model_routing_resolver
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.consistency.ref_index import CrossFeatureRefIndexImpl


async def get_consistency_service(
    session: SessionDep,
    user_id: CurrentUserIdDep,
    novel_id: uuid.UUID,
) -> ConsistencyCheckerService:
    """Create a ConsistencyCheckerService with per-user LAZY model routing.

    Production wiring:
    - TWO ``LazyModelResolution``s (ADR-086 L13) around the per-user
      model cascade (FACT_EXTRACT + CONSISTENCY intents, verbatim eager
      order and args); both resolve at the service's first use — after
      the novel ownership gate — so request-validation errors surface
      as 422 before any routing cascade runs.
      ``ConfigurationError`` propagates loudly at first use (RULE-11;
      consistency routers are auth-mandatory).
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - ConsistencyOrchestrator for staged pipeline (ADR-044), carrying
      the lazy cascades for both stages
    - Repositories for data access
    - TokenLimitsService for dynamic context cap resolution

    FastAPI resolves ``novel_id`` from the endpoints' declared
    ``novel_id`` parameter, ``user_id`` via ``CurrentUserIdDep``, and the
    session via ``SessionDep``.
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.checker_service import ConsistencyCheckerService
    from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    uid = uuid.UUID(user_id)
    resolver = get_model_routing_resolver(session)
    # Dual lazy wiring (ADR-086 L13): one LazyModelResolution per intent
    # — neither cascade runs at construction; both resolve at the
    # service's first use, after the novel ownership gate.
    fact_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.FACT_EXTRACT, uid, novel_id)
    )
    consistency_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.CONSISTENCY, uid, novel_id)
    )

    registry = get_model_registry()
    composer = get_composer()
    invocation_pipeline = get_invocation_pipeline()

    # Repositories
    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)
    timeline_repo = TimelineEventRepository(session)

    # Orchestrator for staged pipeline — carries the lazy cascades for
    # BOTH stages (extractor + checker); credentials thread through at
    # the orchestrator's first-use composition.
    orchestrator = ConsistencyOrchestrator(
        registry=registry,
        fact_extractor_resolution=fact_resolution,
        consistency_resolution=consistency_resolution,
        composer=composer,
        invocation_pipeline=invocation_pipeline,
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
        registry=registry,
        consistency_resolution=consistency_resolution,
        composer=composer,
        token_limits_service=token_limits_service,
        orchestrator=orchestrator,
        invocation_pipeline=invocation_pipeline,
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
