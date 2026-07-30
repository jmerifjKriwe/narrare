"""DI factories for the Series module (RULE-06: router → service → repository).

Three factories wire the request-scoped async session into the Series
repositories and services. The join-service factory builds every repository
it needs (series/novel/kb) from the same session so the whole join
transaction commits/rolls back together.
"""

from __future__ import annotations

from narrare._app.dependencies import SessionDep  # noqa: TC001 - runtime FastAPI DI annotation
from narrare.series.join_service import SeriesJoinService
from narrare.series.repository import SeriesRepository
from narrare.series.service import SeriesService


def get_series_repository(session: SessionDep) -> SeriesRepository:
    """Request-scoped SeriesRepository."""
    return SeriesRepository(session)


def get_series_service(session: SessionDep) -> SeriesService:
    """Request-scoped SeriesService (CRUD + settings + novels-in-series)."""
    return SeriesService(SeriesRepository(session))


def get_series_join_service(session: SessionDep) -> SeriesJoinService:
    """Request-scoped SeriesJoinService (Policy alpha preview/apply/remove).

    All repositories share ``session`` so membership mutations and KB scope
    promotions commit as one transaction.
    """
    # Local imports keep the module import-light at app startup.
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository

    return SeriesJoinService(
        session=session,
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        kb_repo=KBRepository(session),
    )
