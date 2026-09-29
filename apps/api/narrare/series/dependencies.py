"""DI factories for the Series module (RULE-06: router → service → repository).

Three factories wire the request-scoped async session into the Series
repositories and services. The join-service factory builds every repository
it needs (series/novel/kb) from the same session so the whole join
transaction commits/rolls back together.

Band-summary wiring (the anti-enumeration guard, the shared
``build_band_summary_service`` builder, and ``get_band_summary_service``)
lives in ``dependencies_band_summary.py`` (RULE-04 split — this file's
200-line dependency-module limit); the ADR-082 slider-preview wiring in
``dependencies_context_preview.py``; the voice/consistency/drift wiring in
their sibling ``dependencies_*.py`` modules.
"""

from __future__ import annotations

from narrare._app.dependencies import (  # noqa: TC001 — needed at runtime for FastAPI DI
    SessionDep,
)
from narrare.novels.repository import NovelRepository
from narrare.series.join_service import SeriesJoinService
from narrare.series.repository import SeriesRepository
from narrare.series.service import SeriesService


def get_series_repository(session: SessionDep) -> SeriesRepository:
    """Request-scoped SeriesRepository."""
    return SeriesRepository(session)


def get_series_service(session: SessionDep) -> SeriesService:
    """Request-scoped SeriesService (CRUD + settings + novels-in-series).

    Wires the band-summary auto-trigger enqueuer (Spec 2 Task 5) so that
    ``update_series`` can launch background generation in-process when a
    series transitions to ``completed``. The enqueuer is resolved lazily
    inside the function body to avoid a module-level circular import
    (``series.service`` ← ``series.tasks`` ← ``series.dependencies``).
    """
    from narrare.series.tasks import enqueue_band_summary_generation

    return SeriesService(
        SeriesRepository(session),
        enqueue_band_summary=enqueue_band_summary_generation,
    )


def get_series_join_service(session: SessionDep) -> SeriesJoinService:
    """Request-scoped SeriesJoinService (Policy alpha preview/apply/remove).

    All repositories share ``session`` so membership mutations and KB scope
    promotions commit as one transaction.
    """
    # Local imports keep the module import-light at app startup.
    from narrare.kb.repository import KBRepository

    return SeriesJoinService(
        session=session,
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        kb_repo=KBRepository(session),
    )
