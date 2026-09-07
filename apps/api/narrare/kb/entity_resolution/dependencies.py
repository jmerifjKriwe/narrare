"""Entity-resolution dependency factories (ADR-085 P3, RULE-19).

Wiring only — no business logic. The analysis service is assembled from
its three injected collaborators (snapshot builder, pure scoring engine,
novel-scoped analysis cache); the scope guard enforces novel ownership
before any route handler runs, against the same repository the novels
domain uses, so it stays overridable in route tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    CurrentUserIdDep,  # noqa: TC001 - FastAPI DI runtime
    SessionDep,  # noqa: TC001 - FastAPI DI runtime
)
from narrare.novels.repository import NovelRepository

if TYPE_CHECKING:
    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService


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


def get_resolution_analyzer(session: SessionDep) -> ResolutionAnalysisService:
    """Wire the analysis service: snapshot builder + pure engine + cache.

    The engine is I/O-free (narrare_core); all persistence flows through
    the session-bound KB/relationship repositories inside the builder.
    The in-memory cache backend follows the consistency-cache wiring
    (ADR-080).
    """
    from narrare.kb.entity_resolution.analysis_service import (
        ResolutionAnalysisCache,
        ResolutionAnalysisService,
    )
    from narrare.kb.entity_resolution.snapshot_service import SnapshotBuilder
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare_core.cache import InMemorySessionCache
    from narrare_core.kb.resolution.scoring import ResolutionEngine

    return ResolutionAnalysisService(
        builder=SnapshotBuilder(KBRepository(session), RelationshipRepository(session)),
        engine=ResolutionEngine(),
        cache=ResolutionAnalysisCache(InMemorySessionCache()),
    )
