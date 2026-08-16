"""DI factory for drift persistence (SERIES-004 Slice 6, C2).

Split into its own module (RULE-04 — the ``dependencies_{consistency,
voice_drift}.py`` precedent; ``dependencies.py`` is at 179/200 lines, NOT at
the limit — the split follows the established per-feature dependency-module
pattern rather than a size necessity). The factory
CHAINS the two existing run-service factories via ``Depends`` (their wiring is
not duplicated) and adds the snapshot read/write dependencies: series + novel
+ chapter repositories (ownership + fingerprint reads) and the drift-results
repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends

from narrare._app.dependencies import (  # noqa: TC001 — FastAPI resolves the dependency signature at runtime
    SessionDep,
)
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.series.dependencies_consistency import get_series_consistency_service
from narrare.series.dependencies_voice_drift import get_series_voice_drift_service
from narrare.series.repository import SeriesRepository
from narrare.series.series_drift_repository import SeriesDriftRepository

if TYPE_CHECKING:
    from narrare.series.series_consistency_service import SeriesConsistencyService
    from narrare.series.series_drift_persistence_service import (
        SeriesDriftPersistenceService,
    )
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService


def get_series_drift_persistence_service(
    session: SessionDep,
    consistency_service: SeriesConsistencyService = Depends(  # noqa: B008 — FastAPI DI pattern
        get_series_consistency_service
    ),
    voice_drift_service: SeriesVoiceDriftService = Depends(  # noqa: B008 — FastAPI DI pattern
        get_series_voice_drift_service
    ),
) -> SeriesDriftPersistenceService:
    """Request-scoped SeriesDriftPersistenceService (C2 drift persistence).

    Wraps the two run services (wired by their existing factories — Depends-
    chained, not duplicated) with the snapshot persistence dependencies.
    """
    from narrare.series.series_drift_persistence_service import (
        SeriesDriftPersistenceService,
    )

    return SeriesDriftPersistenceService(
        consistency_service=consistency_service,
        voice_drift_service=voice_drift_service,
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        drift_repo=SeriesDriftRepository(session),
    )
