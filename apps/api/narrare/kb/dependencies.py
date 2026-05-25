"""KB dependency injection factories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
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
