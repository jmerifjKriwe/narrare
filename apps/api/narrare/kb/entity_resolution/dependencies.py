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
from narrare.kb.entity_resolution._dismissal_store import (  # noqa: TC001 - FastAPI DI runtime
    ResolutionDismissalStore,
)
from narrare.kb.entity_resolution.adjudicator import (  # noqa: TC001 - FastAPI DI runtime
    UncertainBandAdjudicator,
)
from narrare.kb.entity_resolution.analysis_service import (  # noqa: TC001 - FastAPI DI runtime
    ResolutionAnalysisService,
)
from narrare.kb.entity_resolution.dependencies_adjudicator import (
    get_merge_adjudicator,
)
from narrare.kb.entity_resolution.endorse_service import (  # noqa: TC001 - FastAPI DI runtime
    ResolutionEndorseService,
)
from narrare.kb.entity_resolution.merge_executor import (  # noqa: TC001 - FastAPI DI runtime
    MergeExecutor,
)
from narrare.kb.relationship_repository import (  # noqa: TC001 - FastAPI DI runtime
    RelationshipRepository,
)
from narrare.kb.repository import KBRepository  # noqa: TC001 - FastAPI DI runtime
from narrare.novels.repository import NovelRepository

if TYPE_CHECKING:
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


def get_resolution_dismissal_store(session: SessionDep) -> ResolutionDismissalStore:
    """Wire the rejection ledger over the existing dismissed-findings table."""
    from narrare.kb.dismissed_repository import DismissedFindingRepository
    from narrare.kb.entity_resolution._dismissal_store import ResolutionDismissalStore

    return ResolutionDismissalStore(DismissedFindingRepository(session))


def get_merge_executor(
    kb_repo: Annotated[KBRepository, Depends(get_kb_repository)],
    rel_repo: Annotated[RelationshipRepository, Depends(get_rel_repository)],
    session: SessionDep,
) -> MergeExecutor:
    """Wire the merge executor (savepoint owner = request session)."""
    from narrare.kb.entity_resolution.merge_executor import MergeExecutor

    return MergeExecutor(kb_repo=kb_repo, rel_repo=rel_repo, session=session)


def _build_analyzer(
    kb_repo: KBRepository,
    rel_repo: RelationshipRepository,
    dismissed: ResolutionDismissalStore,
    *,
    adjudicator: UncertainBandAdjudicator | None = None,
) -> ResolutionAnalysisService:
    """Assemble the analysis service from its injected collaborators.

    Shared by the deterministic analyzer (endorse/suggestions re-validation
    and cache reads) and the adjudicated analyzer (analyze route).
    """
    from narrare.kb.entity_resolution.analysis_cache import ResolutionAnalysisCache
    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
    from narrare.kb.entity_resolution.snapshot_service import SnapshotBuilder
    from narrare_core.kb.resolution.scoring import ResolutionEngine

    return ResolutionAnalysisService(
        builder=SnapshotBuilder(kb_repo, rel_repo),
        engine=ResolutionEngine(),
        cache=ResolutionAnalysisCache(_get_cache_backend()),
        dismissed=dismissed,
        adjudicator=adjudicator,
    )


def get_resolution_analyzer(
    kb_repo: Annotated[KBRepository, Depends(get_kb_repository)],
    rel_repo: Annotated[RelationshipRepository, Depends(get_rel_repository)],
    dismissed: Annotated[ResolutionDismissalStore, Depends(get_resolution_dismissal_store)],
) -> ResolutionAnalysisService:
    """Wire the DETERMINISTIC analyzer: snapshot builder + pure engine + cache.

    The kb/relationship repositories come from the canonical kb factories
    (overridable seam — route tests inject fakes there while this factory
    and the scope guard run for real). No adjudicator: endorse
    re-validation and cache reads never touch the LLM (spec §8).
    """
    return _build_analyzer(kb_repo, rel_repo, dismissed)


def get_adjudicated_analyzer(
    kb_repo: Annotated[KBRepository, Depends(get_kb_repository)],
    rel_repo: Annotated[RelationshipRepository, Depends(get_rel_repository)],
    dismissed: Annotated[ResolutionDismissalStore, Depends(get_resolution_dismissal_store)],
    adjudicator: Annotated[UncertainBandAdjudicator, Depends(get_merge_adjudicator)],
) -> ResolutionAnalysisService:
    """Wire the ADJUDICATED analyzer (analyze route only, ADR-085 P5).

    Same deterministic core plus the uncertain-band annotation: REVIEW
    pairs may be LLM-adjudicated through the existing KBMergeService; a
    failure degrades to a note (RULE-11), never a crashed analysis.
    """
    return _build_analyzer(kb_repo, rel_repo, dismissed, adjudicator=adjudicator)


def get_endorse_service(
    analyzer: Annotated[ResolutionAnalysisService, Depends(get_resolution_analyzer)],
    executor: Annotated[MergeExecutor, Depends(get_merge_executor)],
    kb_repo: Annotated[KBRepository, Depends(get_kb_repository)],
    rel_repo: Annotated[RelationshipRepository, Depends(get_rel_repository)],
    dismissals: Annotated[ResolutionDismissalStore, Depends(get_resolution_dismissal_store)],
) -> ResolutionEndorseService:
    """Wire the endorse/reject adjudication service (spec §7)."""
    from narrare.kb.entity_resolution.endorse_service import ResolutionEndorseService

    return ResolutionEndorseService(
        analyzer=analyzer,
        executor=executor,
        kb_repo=kb_repo,
        rel_repo=rel_repo,
        dismissals=dismissals,
    )
