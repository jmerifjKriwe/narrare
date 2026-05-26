"""Analysis dependency injection factories."""

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
    - ChapterRepository + KBRepository + NovelRepository for context
    - RedisSessionCache for result caching (30min TTL)
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import get_composer, get_model_registry
    from narrare.analysis.beta_reader_cache import BetaReaderCache
    from narrare.analysis.beta_reader_service import BetaReaderService
    from narrare.analysis.context_assembler import ContextAssembler
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.cache.redis_client import RedisSessionCache
    from narrare_core.llm.intents import ResolvedModelConfig

    registry = get_model_registry()
    composer = get_composer()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.7,
        max_tokens=4096,
    )

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
    )
