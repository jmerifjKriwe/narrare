"""Analysis dependency injection factories.

Feature-specific beta-reader wiring lives in
:mod:`narrare.analysis.dependencies_beta_reader` (RULE-04 split) and
coreference wiring in :mod:`narrare.analysis.dependencies_coreference`.
This module holds the remaining analysis factories.

Model acquisition follows the per-user model-routing cascade with LAZY
first-use resolution (ADR-086): the LLM-backed factories wire a
``LazyModelResolution`` around ``resolver.resolve(LLMIntent.ANALYSE,
user_id, novel_id)`` — no resolution at construction (FastAPI solves all
sub-dependencies BEFORE body validation, so an eager resolve here would
preempt legitimate 422s). The routing cascade runs at the service's
first use, inside the service layer. The sentiment factory stays
deterministic (ADR-021, no LLM). No business logic lives here — only
wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_current_user_id,
)
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.analysis.services.pov_service import POVService
    from narrare.analysis.services.readability_service import ReadabilityService
    from narrare.analysis.services.sentiment_service import ChapterSentimentService


def get_sentiment_service(session: SessionDep) -> ChapterSentimentService:
    """Create a ChapterSentimentService with injected dependencies.

    Production wiring:
    - ChapterRepository for chapter content fetching.
    - NovelRepository for novel access control + language resolution.
    - SpacyNLPProvider for sentence splitting and linguistic features.

    Unlike ``get_beta_reader_service``, this factory does **not** require
    model registry, prompt composer, or cache — sentiment analysis is a
    purely deterministic computation (ADR-021) with no LLM calls.
    """
    from narrare.analysis.services.sentiment_service import ChapterSentimentService
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.nlp.provider_spacy import SpacyNLPProvider

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    nlp_provider = SpacyNLPProvider()

    return ChapterSentimentService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        nlp_provider=nlp_provider,
    )


async def get_readability_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> ReadabilityService:
    """Create a ReadabilityService with lazily-wired per-user routing.

    FastAPI dependency: novel_id comes from the endpoint's query parameter,
    user_id and session are resolved via Depends. The routing cascade
    (ANALYSE for this user + novel) resolves at the service's FIRST USE —
    NOT here (ADR-086): construction happens pre-body-validation, and
    eager resolution would preempt legitimate 422s (and the P2 novel
    guard would preempt them with 404s). ``ConfigurationError`` propagates
    loudly at first use (RULE-11; analysis routers are auth-mandatory).

    Production wiring:
    - ChapterRepository for chapter content fetching.
    - NovelRepository for novel access control + language resolution.
    - ModelRegistry + lazy ModelResolution (ADR-086) for the
      ReadabilityAgent (AI-powered sentence analysis).
    - PromptComposer for Mode 1 (composer-driven) system prompt assembly (ADR-048).
    - Canonical KB-context provider (ADR-067) for the kb_* slots (audit N12).
    - InvocationPipeline for invocation evidence (ADR-040).

    Phase 1 (deterministic metrics) requires no LLM calls.
    Phase 2 (AI sentence analysis) uses the ReadabilityAgent via
    ModelRegistry.
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.analysis.services.readability_service import ReadabilityService
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.ANALYSE, UUID(user_id), novel_id)
    )

    registry = get_model_registry()

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    # Canonical KB-context provider (ADR-067) — same supply as get_pov_service (B07).
    kb_provider = KBContextProvider(
        kb_repo=KBRepository(session), relationship_repo=RelationshipRepository(session)
    )

    return ReadabilityService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        model_registry=registry,
        model_resolution=model_resolution,
        composer=get_composer(),
        kb_context_provider=kb_provider,
        invocation_pipeline=get_invocation_pipeline(),
    )


async def get_pov_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> POVService:
    """Create a POVService with lazily-wired per-user routing.

    FastAPI dependency: novel_id comes from the endpoint's query parameter,
    user_id and session are resolved via Depends. The routing cascade
    (ANALYSE for this user + novel) resolves at the service's FIRST USE —
    NOT here (ADR-086): construction happens pre-body-validation, and
    eager resolution would preempt legitimate 422s (and the P2 novel
    guard would preempt them with 404s). ``ConfigurationError`` propagates
    loudly at first use (RULE-11; analysis routers are auth-mandatory).

    Production wiring:
    - ChapterRepository for chapter content fetching.
    - NovelRepository for novel access control + language resolution.
    - ModelRegistry + lazy ModelResolution (ADR-086) for the
      POVDetectionAgent (AI-powered scene detection + violation analysis).
    - Canonical KB-context provider (ADR-067) for the ``kb_characters`` /
      ``kb_locations`` / ``kb_factions`` / ``kb_relationships`` prompt
      variables — rendered through the ADR-050 envelope with provenance
      (FIND-017). Degrades gracefully (RULE-11).
    - PromptComposer for Mode 1 (composer-driven) system prompt assembly (ADR-048).
    - InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.analysis.services.pov_service import POVService
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.ANALYSE, UUID(user_id), novel_id)
    )

    registry = get_model_registry()

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    # Canonical KB-context provider (ADR-067): single fetch+render source for
    # the pov template's kb_* slots. Degrades gracefully (RULE-11).
    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    return POVService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        model_registry=registry,
        model_resolution=model_resolution,
        composer=get_composer(),
        kb_context_provider=kb_context_provider,
        invocation_pipeline=get_invocation_pipeline(),
    )
