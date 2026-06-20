"""Analysis dependency injection factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.analysis.beta_reader_service import BetaReaderService
    from narrare.analysis.services.pov_service import POVService
    from narrare.analysis.services.readability_service import ReadabilityService
    from narrare.analysis.services.sentiment_service import ChapterSentimentService


def get_beta_reader_service(session: SessionDep) -> BetaReaderService:
    """Create a BetaReaderService with injected dependencies.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - ChapterRepository + KBRepository + NovelRepository for context
    - RedisSessionCache for result caching (30min TTL)
    - InvocationPipeline for invocation evidence (ADR-040)
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
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.cache.redis_client import RedisSessionCache

    registry = get_model_registry()
    composer = get_composer()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)
    invocation_pipeline = get_invocation_pipeline()

    # Repositories
    chapter_repo = ChapterRepository(session)
    kb_repo = KBRepository(session)
    novel_repo = NovelRepository(session)

    # Context assembler
    assembler = ContextAssembler(
        chapter_repo=chapter_repo,
        kb_repo=kb_repo,
        novel_repo=novel_repo,
    )

    # Redis-backed cache with 30min TTL
    settings = get_settings()
    redis_cache = RedisSessionCache(settings.redis_url)
    beta_cache = BetaReaderCache(redis_cache)

    return BetaReaderService(
        context_assembler=assembler,
        cache=beta_cache,
        registry=registry,
        config=config,
        composer=composer,
        invocation_pipeline=invocation_pipeline,
    )


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


def get_readability_service(session: SessionDep) -> ReadabilityService:
    """Create a ReadabilityService with injected dependencies.

    Production wiring:
    - ChapterRepository for chapter content fetching.
    - NovelRepository for novel access control + language resolution.
    - ModelRegistry + ResolvedModelConfig for the ReadabilityAgent
      (AI-powered sentence analysis).
    - InvocationPipeline for invocation evidence (ADR-040).

    Phase 1 (deterministic metrics) requires no LLM calls.
    Phase 2 (AI sentence analysis) uses the ReadabilityAgent via
    ModelRegistry.
    """
    from narrare._app.dependencies import (
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.analysis.services.readability_service import ReadabilityService
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

    registry = get_model_registry()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)

    return ReadabilityService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        model_registry=registry,
        model_config=config,
        invocation_pipeline=get_invocation_pipeline(),
    )


def get_pov_service(session: SessionDep) -> POVService:
    """Create a POVService with injected dependencies.

    Production wiring:
    - ChapterRepository for chapter content fetching.
    - NovelRepository for novel access control + language resolution.
    - KBRepository for resolving known character names from KB.
    - ModelRegistry + ResolvedModelConfig for the POVDetectionAgent
      (AI-powered scene detection + violation analysis).
    - InvocationPipeline for invocation evidence (ADR-040).
    """
    from narrare._app.dependencies import (
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.analysis.services.pov_service import POVService
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    registry = get_model_registry()
    config = build_system_default_config(SystemModelCategory.ANALYSIS)

    chapter_repo = ChapterRepository(session)
    novel_repo = NovelRepository(session)
    kb_repo = KBRepository(session)

    return POVService(
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
        kb_repo=kb_repo,
        model_registry=registry,
        model_config=config,
        invocation_pipeline=get_invocation_pipeline(),
    )
