"""Analysis dependency injection factory — beta reader (RULE-04 split).

Extracted from ``dependencies.py`` to keep that file under the 200-line
dependency-file limit (RULE-04). Production wiring for ``BetaReaderService``
lives here.

See:
    ADR-067 — Reusable KB-Context Provider (KB context routing)
    CONSTRAINTS.md RULE-04/06/07/11
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 — needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.analysis.beta_reader_service import BetaReaderService


def get_beta_reader_service(session: SessionDep) -> BetaReaderService:
    """Create a BetaReaderService with injected dependencies.

    Production wiring:
    - ModelRegistry for LLM model resolution
    - PromptComposer for system prompt assembly
    - ChapterRepository + NovelRepository for context
    - Canonical KBContextProvider (ADR-067) for kb_characters / kb_locations,
      rendered through the ADR-050 envelope with provenance (FIND-017).
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
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.cache.redis_client import RedisSessionCache

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
