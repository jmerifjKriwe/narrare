"""KB dependency injection — core repos, services, graph, and suggest."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI
from narrare.events.publisher import (
    WikiEventPublisherDep,  # noqa: TC001 - needed at runtime for FastAPI DI
)

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
    """Create a KBScopeService (scope-toggle wiring: KB + Novel + Series repos).

    The scope toggle verifies NOVEL ownership (promote) / SERIES + target-novel
    ownership (demote), so all three repositories share ``session`` — ownership
    lookups and the scope mutation run in one transaction.
    """
    from narrare.kb.repository import KBRepository
    from narrare.kb.scope_service import KBScopeService
    from narrare.novels.repository import NovelRepository
    from narrare.series.repository import SeriesRepository

    return KBScopeService(
        KBRepository(session),
        NovelRepository(session),
        SeriesRepository(session),
    )


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


def get_kb_service(
    session: SessionDep,
    event_publisher: WikiEventPublisherDep,
) -> KBService:
    """Create a KBService with injected dependencies.

    ``event_publisher`` is the in-process wiki EventPublisher bound on
    ``app.state`` by the lifespan (Q-016). It is ``None`` when the lifespan
    failed to initialise it (graceful degradation — KB updates proceed
    without firing wiki-regeneration events).
    """
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
        event_publisher=event_publisher,
    )


def get_rel_repository(
    session: SessionDep,
) -> RelationshipRepository:
    """Create a RelationshipRepository with the given session."""
    from narrare.kb.relationship_repository import RelationshipRepository

    return RelationshipRepository(session)


def get_rel_service(session: SessionDep) -> RelationshipService:
    """Create a RelationshipService with injected dependencies.

    NovelRepository backs the read/write ownership gate (IDOR fix S10).
    """
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.relationship_service import RelationshipService
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    return RelationshipService(
        rel_repo=RelationshipRepository(session),
        entry_repo=KBRepository(session),
        novel_repo=NovelRepository(session),
    )


def get_kb_suggest_service(session: SessionDep) -> KBSuggestService:
    """Create a KBSuggestService with injected dependencies.

    The embedded ``EmbeddingService`` (the ``EmbeddingStoreProtocol`` behind
    ``ProactiveContextService`` — the only production caller of
    ``EmbeddingService.search``) carries the opt-in ADR-090 rerank tier:

    - Flag off (shipped default): constructed exactly as before the tier
      existed — repo only, the component builder is never consulted.
    - Flag on: the same ``build_rerank_components`` DI the admin embedding
      routes use supplies the reranker (pinned settings checkpoint) and the
      KB text fetcher (``KBRepository.get_bodies_by_ids`` — the right
      supplier for ``source_type="kb_entry"``). The stage reorders search
      candidates before the cut; because ``ProactiveContextService``
      re-scores its candidates in Stage 3, rerank here changes candidate
      *membership* — which entries reach the prompt context — more than
      their final order. That is the intended benefit (better candidates
      in), not a prompt-ordering change.
    """
    from narrare.chapters.repository import ChapterRepository
    from narrare.embeddings.dependencies import build_rerank_components
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.kb.repository import KBRepository
    from narrare.kb.suggest_service import KBSuggestService
    from narrare.novels.repository import NovelRepository
    from narrare_core.context.proactive_service import ProactiveContextService
    from narrare_core.settings import get_core_settings

    # EmbeddingService implements EmbeddingStoreProtocol (takes text, not vectors).
    # LSP flags reprocess() return-type mismatch, but ProactiveContextService
    # never calls reprocess — the four methods it uses are structurally compatible.
    embedding_repo = EmbeddingRepository(session)
    if get_core_settings().embedding_rerank_enabled:
        reranker, text_fetcher = build_rerank_components(session)
        embedding_service = EmbeddingService(
            embedding_repo,
            reranker=reranker,
            text_fetcher=text_fetcher,
        )
    else:
        # Shipped default: byte-identical pre-rerank construction — the
        # builder is not consulted, no components, no logs (RULE-11: the
        # stage stays inert until explicitly opted in).
        embedding_service = EmbeddingService(embedding_repo)
    proactive = ProactiveContextService(
        embedding_store=cast("EmbeddingStoreProtocol", embedding_service)
    )
    return KBSuggestService(
        proactive_context=proactive,
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
        novel_repo=NovelRepository(session),
    )


def get_graph_service(session: SessionDep) -> GraphService:
    """Create a GraphService with injected dependencies.

    Production wiring: uses KBRepository and RelationshipRepository
    for data access. No LLM calls — pure data transformation.
    NovelRepository backs the read-ownership gate (IDOR fix S9).
    """
    from narrare.kb.graph_service import GraphService
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    return GraphService(
        kb_repo=KBRepository(session),
        rel_repo=RelationshipRepository(session),
        novel_repo=NovelRepository(session),
    )
