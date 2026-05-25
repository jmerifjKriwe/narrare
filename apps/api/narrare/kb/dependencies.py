"""KB dependency injection factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare.kb.session_service import KBSessionService
    from narrare.kb.suggest_service import KBSuggestService


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
    For session storage, uses InMemorySessionCache as a temporary measure
    until Redis is wired through the app lifespan.
    """
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.kb.assist_service import KBAssistService
    from narrare.kb.session_service import KBSessionService
    from narrare.kb.session_store import KBCreationSessionStore

    # Session storage: InMemorySessionCache as temp until Redis DI wired up.
    # See TODO in session_store.py for Redis integration.
    from narrare.writing._ws_cache import InMemorySessionCache
    from narrare_core.context.proactive_service import ProactiveContextService

    cache = InMemorySessionCache()
    session_store = KBCreationSessionStore(cache=cache)  # type: ignore[arg-type]

    # ProactiveContextService with real embedding service
    embedding_service = EmbeddingService(EmbeddingRepository(session))
    proactive = ProactiveContextService(embedding_store=embedding_service)  # type: ignore[arg-type]

    # KBAssistService with real ModelRegistry + PromptComposer.
    # Temporarily uses TestModel until app-level DI provides ModelRegistry.
    # This is acceptable for initial integration — the session endpoint
    # will return 503 until a real model is configured in the app lifespan.
    # narrare: allow-direct-llm
    # Temporary placeholder until app-level DI provides real ModelRegistry.
    from pydantic_ai.models.test import (
        TestModel as _TestModel,
    )

    model = _TestModel()
    # PromptComposer requires registry + meta_loader which need file I/O.
    # Production wiring will inject these from the app state.
    # For now, create a minimal composer that loads bundled prompts.
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.prompts.meta import MetaPromptLoader
    from narrare_core.prompts.registry import PromptRegistry

    registry = PromptRegistry()
    meta_loader = MetaPromptLoader()
    composer = PromptComposer(registry=registry, meta_loader=meta_loader)

    assist_service = KBAssistService(
        model=model,
        proactive_context=proactive,
        prompt_composer=composer,
    )

    return KBSessionService(
        session_store=session_store,
        assist_service=assist_service,
    )
