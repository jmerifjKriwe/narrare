"""KB dependency injection factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.consistency_service import KBConsistencyService
    from narrare.kb.extraction_service import ExtractionService
    from narrare.kb.graph_service import GraphService
    from narrare.kb.improve_service import KBImproveService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare.kb.session_service import KBSessionService
    from narrare.kb.suggest_service import KBSuggestService
    from narrare.kb.worldbuilding_service import WorldbuildingService


def get_kb_repository(session: SessionDep) -> KBRepository:
    """Create a KBRepository with the given session."""
    from narrare.kb.repository import KBRepository

    return KBRepository(session)


def get_kb_service(session: SessionDep) -> KBService:
    """Create a KBService with injected dependencies."""
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.kb.embedding_hooks import EmbeddingHookManager
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare.novels.repository import NovelRepository

    embedding_hooks = EmbeddingHookManager(
        embedding_repo=EmbeddingRepository(session),
    )
    return KBService(
        repo=KBRepository(session),
        novel_repo=NovelRepository(session),
        embedding_hooks=embedding_hooks,
    )


def get_rel_repository(
    session: SessionDep,
) -> RelationshipRepository:
    """Create a RelationshipRepository with the given session."""
    from narrare.kb.relationship_repository import RelationshipRepository

    return RelationshipRepository(session)


def get_rel_service(session: SessionDep) -> RelationshipService:
    """Create a RelationshipService with injected dependencies."""
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository

    return RelationshipService(
        rel_repo=RelationshipRepository(session),
        entry_repo=KBRepository(session),
    )


def get_extraction_service(session: SessionDep) -> ExtractionService:
    """Create an ExtractionService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, and ChapterRepository + KBRepository for data.

    Also injects KBService and RelationshipRepository for the apply
    extraction step (KB-007).
    """
    from narrare._app.dependencies import get_composer, get_model_registry
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.extraction_service import ExtractionService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare_core.llm.intents import ResolvedModelConfig

    registry = get_model_registry()
    composer = get_composer()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.7,
        max_tokens=4096,
    )

    return ExtractionService(
        registry=registry,
        config=config,
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
        composer=composer,
        kb_service=KBService(
            repo=KBRepository(session),
            novel_repo=None,
            embedding_hooks=None,
        ),
        rel_repo=RelationshipRepository(session),
    )


def get_kb_suggest_service(session: SessionDep) -> KBSuggestService:
    """Create a KBSuggestService with injected dependencies."""
    from narrare.chapters.repository import ChapterRepository
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.kb.repository import KBRepository
    from narrare.kb.suggest_service import KBSuggestService
    from narrare_core.context.proactive_service import ProactiveContextService

    # EmbeddingService implements EmbeddingStoreProtocol (takes text, not vectors).
    # LSP flags reprocess() return-type mismatch, but ProactiveContextService
    # never calls reprocess — the four methods it uses are structurally compatible.
    embedding_service = EmbeddingService(EmbeddingRepository(session))
    proactive = ProactiveContextService(embedding_store=embedding_service)  # type: ignore[arg-type]
    return KBSuggestService(
        proactive_context=proactive,
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
    )


def get_kb_session_service(session: SessionDep) -> KBSessionService:
    """Create a KBSessionService with injected dependencies.

    Production wiring: uses EmbeddingService for ProactiveContextService,
    ModelRegistry for LLM model, and PromptComposer for system prompts.
    For session storage, uses RedisSessionCache for persistence with TTL.
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import get_composer, get_model_registry
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.kb.assist_service import KBAssistService
    from narrare.kb.session_service import KBSessionService
    from narrare.kb.session_store import KBCreationSessionStore
    from narrare_core.cache.redis_client import RedisSessionCache
    from narrare_core.context.proactive_service import ProactiveContextService
    from narrare_core.llm.intents import ResolvedModelConfig

    # Session storage: Redis-backed with 30min TTL.
    settings = get_settings()
    cache = RedisSessionCache(settings.redis_url)
    session_store = KBCreationSessionStore(cache=cache)

    # ProactiveContextService with real embedding service
    embedding_service = EmbeddingService(EmbeddingRepository(session))
    proactive = ProactiveContextService(embedding_store=embedding_service)  # type: ignore[arg-type]

    # KBAssistService with real ModelRegistry + PromptComposer.
    registry = get_model_registry()
    composer = get_composer()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.7,
        max_tokens=4096,
    )

    assist_service = KBAssistService(
        registry=registry,
        config=config,
        proactive_context=proactive,
        prompt_composer=composer,
    )

    kb_service = get_kb_service(session)

    return KBSessionService(
        session_store=session_store,
        assist_service=assist_service,
        kb_service=kb_service,
    )


def get_kb_improve_service(session: SessionDep) -> KBImproveService:
    """Create a KBImproveService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, ProactiveContextService for world context,
    and KBRepository + KBService + RelationshipRepository for data access.
    Uses Redis-backed KBImproveCache for 10min TTL on analysis results.
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import get_composer, get_model_registry
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare.kb.improve_cache import KBImproveCache
    from narrare.kb.improve_service import KBImproveService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.cache.redis_client import RedisSessionCache
    from narrare_core.context.proactive_service import ProactiveContextService
    from narrare_core.llm.intents import ResolvedModelConfig

    registry = get_model_registry()
    composer = get_composer()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.7,
        max_tokens=4096,
    )

    kb_repo = KBRepository(session)
    embedding_service = EmbeddingService(EmbeddingRepository(session))
    proactive = ProactiveContextService(embedding_store=embedding_service)  # type: ignore[arg-type]
    kb_service = get_kb_service(session)

    # Redis-backed improve cache with 10min TTL
    settings = get_settings()
    redis_cache = RedisSessionCache(settings.redis_url)
    improve_cache = KBImproveCache(redis_cache)

    # Analyzer handles all LLM interaction + caching
    analyzer = KBImproveAnalyzer(
        registry=registry,
        config=config,
        proactive_context=proactive,
        prompt_composer=composer,
        kb_repo=kb_repo,
        rel_repo=RelationshipRepository(session),
        improve_cache=improve_cache,
    )

    return KBImproveService(
        analyzer=analyzer,
        kb_repo=kb_repo,
        kb_service=kb_service,
        rel_repo=RelationshipRepository(session),
    )


def get_worldbuilding_service(session: SessionDep) -> WorldbuildingService:
    """Create a WorldbuildingService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, PromptRegistry for prompt resolution, and
    KBRepository + RelationshipRepository for data access.
    Uses Redis-backed WorldbuildingCache for 10min TTL on analysis results.
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import get_composer, get_model_registry, get_registry
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare.kb.worldbuilding_service import WorldbuildingService
    from narrare_core.cache.redis_client import RedisSessionCache
    from narrare_core.llm.intents import ResolvedModelConfig

    registry = get_model_registry()
    composer = get_composer()
    prompt_registry = get_registry()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.7,
        max_tokens=4096,
    )

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)

    # Redis-backed worldbuilding cache with 10min TTL
    settings = get_settings()
    redis_cache = RedisSessionCache(settings.redis_url)
    worldbuilding_cache = WorldbuildingCache(redis_cache)

    # Analyzer handles all LLM interaction + caching
    analyzer = WorldbuildingAnalyzer(
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        registry=registry,
        config=config,
        composer=composer,
        prompt_registry=prompt_registry,
    )

    return WorldbuildingService(
        analyzer=analyzer,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
    )


def get_graph_service(session: SessionDep) -> GraphService:
    """Create a GraphService with injected dependencies.

    Production wiring: uses KBRepository and RelationshipRepository
    for data access. No LLM calls — pure data transformation.
    """
    from narrare.kb.graph_service import GraphService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository

    return GraphService(
        kb_repo=KBRepository(session),
        rel_repo=RelationshipRepository(session),
    )


def get_consistency_service(session: SessionDep) -> KBConsistencyService:
    """Create a KBConsistencyService with injected dependencies.

    Production wiring: uses ModelRegistry for LLM model, PromptComposer
    for system prompts, PromptRegistry for prompt resolution, and
    KBRepository + RelationshipRepository for data access.
    Reuses WorldbuildingAnalyzer for cross-entity Phase 2 consistency.
    Uses Redis-backed ConsistencyCache for 10min TTL on results.
    """
    from narrare._app.config import get_settings
    from narrare._app.dependencies import get_composer, get_model_registry, get_registry
    from narrare.kb.consistency_analyzer import KBConsistencyAnalyzer
    from narrare.kb.consistency_cache import ConsistencyCache
    from narrare.kb.consistency_service import KBConsistencyService
    from narrare.kb.relationship_asymmetry import RelationshipAsymmetryChecker
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare_core.cache.redis_client import RedisSessionCache
    from narrare_core.llm.intents import ResolvedModelConfig

    registry = get_model_registry()
    composer = get_composer()
    prompt_registry = get_registry()
    config = ResolvedModelConfig(
        provider_name="default",
        model_id="default",
        temperature=0.7,
        max_tokens=4096,
    )

    kb_repo = KBRepository(session)
    rel_repo = RelationshipRepository(session)

    # Redis-backed consistency cache with 10min TTL
    settings = get_settings()
    redis_cache = RedisSessionCache(settings.redis_url)
    consistency_cache = ConsistencyCache(redis_cache)

    # Entry-internal analyzer (LLM per entry)
    consistency_analyzer = KBConsistencyAnalyzer(
        kb_repo=kb_repo,
        registry=registry,
        config=config,
        composer=composer,
    )

    # Relationship asymmetry checker (algorithmic, no LLM)
    rel_service = get_rel_service(session)
    asymmetry_checker = RelationshipAsymmetryChecker(
        rel_repo=rel_repo,
        rel_service=rel_service,
    )

    # Worldbuilding analyzer (reused for cross-entity Phase 2)
    worldbuilding_cache = WorldbuildingCache(redis_cache)
    worldbuilding_analyzer = WorldbuildingAnalyzer(
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=worldbuilding_cache,
        registry=registry,
        config=config,
        composer=composer,
        prompt_registry=prompt_registry,
    )

    return KBConsistencyService(
        analyzer=consistency_analyzer,
        asymmetry_checker=asymmetry_checker,
        worldbuilding_analyzer=worldbuilding_analyzer,
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        cache=consistency_cache,
    )
