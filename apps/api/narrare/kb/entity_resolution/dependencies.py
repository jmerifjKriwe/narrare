"""Entity-resolution dependency factories (ADR-085 P3, RULE-19).

Wiring only — no business logic. The analysis service is assembled from
its three injected collaborators (snapshot builder, pure scoring engine,
novel-scoped analysis cache); the scope guard enforces novel ownership
before any route handler runs, against the same repository the novels
domain uses, so it stays overridable in route tests.

The analysis cache backend is a module-level singleton: the cache must
outlive individual requests. A request-scoped backend made every analyze
a miss and starved the GET suggestions contract (fix round 1). Mirrors
the ``kb/_feedback_memory_deps`` mutable-singleton pattern (no
``@lru_cache``); the consistency/worldbuilding per-request caches are a
pre-existing pattern parked separately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    CurrentUserIdDep,  # noqa: TC001 - FastAPI DI runtime
    SessionDep,  # noqa: TC001 - FastAPI DI runtime
)
from narrare.kb.dependencies_core import (
    get_kb_repository,
    get_rel_repository,
)
from narrare.kb.relationship_repository import (  # noqa: TC001 - FastAPI DI runtime
    RelationshipRepository,
)
from narrare.kb.repository import KBRepository  # noqa: TC001 - FastAPI DI runtime
from narrare.novels.repository import NovelRepository

if TYPE_CHECKING:
    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
    from narrare_core.cache import InMemorySessionCache

# Module-level singleton state — mutable, no @lru_cache (mirrors the
# _feedback_memory_deps pattern).
_cache_backend: InMemorySessionCache | None = None


def _get_cache_backend() -> InMemorySessionCache:
    """Return the process-wide analysis cache backend (create-once).

    Single shared ``InMemorySessionCache`` across all requests — the
    backend is the stateful part of the analysis cache; the per-novel
    ``ResolutionAnalysisCache`` wrapper stays stateless over it. Cache
    keys are novel-scoped (``kb:resolution:{novel_id}``), so sharing one
    backend across users/novels is safe.
    """
    global _cache_backend
    if _cache_backend is None:
        from narrare_core.cache import InMemorySessionCache

        _cache_backend = InMemorySessionCache()
    return _cache_backend


def get_novel_scope_repository(session: SessionDep) -> NovelRepository:
    """Create the novel repository used by the scope guard (injectable)."""
    return NovelRepository(session)


async def verify_novel_scope(
    novel_id: UUID,
    user_id: CurrentUserIdDep,
    novel_repo: Annotated[NovelRepository, Depends(get_novel_scope_repository)],
) -> None:
    """Raise ``NotFoundError`` unless ``novel_id`` exists and is owned by the caller.

    404 (not 403) mirrors the kb relationship semantics for foreign-novel
    resources — anti-enumeration: the surface must not reveal whether a
    novel id exists. The global ``NarrareError`` handler maps this to HTTP.
    """
    from narrare_core.shared.errors import NotFoundError

    novel = await novel_repo.get_by_id(novel_id, UUID(user_id))
    if novel is None:
        raise NotFoundError("Novel", identifier=str(novel_id))


def get_resolution_analyzer(
    kb_repo: Annotated[KBRepository, Depends(get_kb_repository)],
    rel_repo: Annotated[RelationshipRepository, Depends(get_rel_repository)],
) -> ResolutionAnalysisService:
    """Wire the analysis service: snapshot builder + pure engine + cache.

    The kb/relationship repositories come from the canonical kb factories
    (overridable seam — route tests inject fakes there while this factory
    and the scope guard run for real). The engine is I/O-free
    (narrare_core); the cache backend is the process-wide singleton.
    """
    from narrare.kb.entity_resolution.analysis_service import (
        ResolutionAnalysisCache,
        ResolutionAnalysisService,
    )
    from narrare.kb.entity_resolution.snapshot_service import SnapshotBuilder
    from narrare_core.kb.resolution.scoring import ResolutionEngine

    return ResolutionAnalysisService(
        builder=SnapshotBuilder(kb_repo, rel_repo),
        engine=ResolutionEngine(),
        cache=ResolutionAnalysisCache(_get_cache_backend()),
    )
