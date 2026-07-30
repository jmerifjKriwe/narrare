"""KB dependency injection — core repos, services, graph, and suggest."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    from narrare.kb.canon_service import KBCanonService
    from narrare.kb.graph_service import GraphService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository
    from narrare.kb.scope_service import KBScopeService
    from narrare.kb.service import KBService
    from narrare.kb.suggest_service import KBSuggestService
    from narrare_core.embeddings.store import EmbeddingStoreProtocol


def get_kb_repository(session: SessionDep) -> KBRepository:
    """Create a KBRepository with the given session."""
    from narrare.kb.repository import KBRepository

    return KBRepository(session)


def get_kb_scope_service(session: SessionDep) -> KBScopeService:
    """Create a KBScopeService with the KB repository (scope-toggle wiring)."""
    from narrare.kb.repository import KBRepository
    from narrare.kb.scope_service import KBScopeService

    return KBScopeService(KBRepository(session))


def get_kb_canon_service(session: SessionDep) -> KBCanonService:
    """Create a KBCanonService with the KB + Series repositories (canon CRUD).

    Both repositories share ``session`` so canon writes and ownership lookups
    run in one transaction. The canon scope is enforced inside the service via
    the ``novel_id IS NULL`` invariant — no extra wiring needed.
    """
    from narrare.kb.canon_service import KBCanonService
    from narrare.kb.repository import KBRepository
    from narrare.series.repository import SeriesRepository

    return KBCanonService(
        kb_repo=KBRepository(session),
        series_repo=SeriesRepository(session),
    )


def get_kb_service(session: SessionDep) -> KBService:
    """Create a KBService with injected dependencies."""
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.kb.embedding_hooks import EmbeddingHookManager
    from narrare.kb.lifecycle_dependencies import get_kb_lifecycle_dispatcher
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
        lifecycle=get_kb_lifecycle_dispatcher(session),
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
    proactive = ProactiveContextService(
        embedding_store=cast("EmbeddingStoreProtocol", embedding_service)
    )
    return KBSuggestService(
        proactive_context=proactive,
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
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
