"""Analysis dependency injection factories.

Feature-specific beta-reader wiring lives in
:mod:`narrare.analysis.dependencies_beta_reader` (RULE-04 split) and
coreference wiring in :mod:`narrare.analysis.dependencies_coreference`.
This module holds the remaining analysis factories.

Model acquisition follows the per-user model-routing cascade: the LLM-backed
factories resolve ``LLMIntent`` for the authenticated user (+ novel for
project-level overrides) and pass the resolved config + credentials into the
services. The sentiment factory stays deterministic (ADR-021, no LLM).
No business logic lives here — only wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_current_user_id,
)
from narrare._app.dependencies_services import get_model_routing_resolver
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
    """Create a ReadabilityService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the endpoint's query parameter,
    user_id and session are resolved via Depends. The model is resolved
    through the per-user cascade; ``ConfigurationError`` propagates when
    the user has no provider configured (analysis routers are
    auth-mandatory).

    Production wiring:
    - ChapterRepository for chapter content fetching.
    - NovelRepository for novel access control + language resolution.
    - ModelRegistry + ResolvedModelConfig for the ReadabilityAgent
      (AI-powered sentence analysis).
    - PromptComposer for Mode 1 (composer-driven) system prompt assembly (ADR-048).
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
    from narrare.novels.repository import NovelRepository

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.ANALYSE,
        UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    return ReadabilityService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        model_registry=registry,
        model_config=resolved.config,
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )


async def get_pov_service(
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> POVService:
    """Create a POVService with per-user resolved model routing.

    FastAPI dependency: novel_id comes from the endpoint's query parameter,
    user_id and session are resolved via Depends. The model is resolved
    through the per-user cascade; ``ConfigurationError`` propagates when
    the user has no provider configured (analysis routers are
    auth-mandatory).

    Production wiring:
    - ChapterRepository for chapter content fetching.
    - NovelRepository for novel access control + language resolution.
    - KBRepository for resolving known character names from KB.
    - ModelRegistry + ResolvedModelConfig for the POVDetectionAgent
      (AI-powered scene detection + violation analysis).
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
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.ANALYSE,
        UUID(user_id),
        novel_id,
    )

    registry = get_model_registry()

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)

    return POVService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        kb_repo=kb_repo,
        model_registry=registry,
        model_config=resolved.config,
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
