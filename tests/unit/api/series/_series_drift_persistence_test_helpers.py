"""Shared builders/fakes for the SeriesDriftPersistenceService unit tests.

RULE-04 split (gate-forced): the brief's single 408-line test module exceeds
both the test hard limit (400, ``check-python-size``) and the architecture
gate's classification for ``*_service.py`` names (300) — so the suite is
modularized the way this directory already handles shared test code
(``_band_summary_test_helpers.py`` /
``_series_consistency_test_helpers.py`` precedent): builders + the
``make_persistence_service`` seam live here; the store-on-run tests stay in
``test_series_drift_persistence_service.py`` and the snapshot-read tests in
``test_series_drift_persistence_snapshot.py``.

The wrapped run services are mocked with AsyncMock at the delegation seam
(the same ADR-030 allowance the router tests use — the run services have
their own exhaustive Fake-based suites and are byte-identical in this slice);
everything else is real: FakeSeriesRepository / FakeNovelRepository /
FakeChapterRepository / FakeSeriesDriftRepository, the REAL fingerprint
(C2 binding: store-time and GET-time share one computation path), and the
REAL Pydantic round-trip through the composite document.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from narrare.chapters.models import Chapter
from narrare.novels.models import Novel
from narrare.series.series_consistency_schemas import (
    SeriesConsistencyCheckResponse,
)
from narrare.series.series_drift_persistence_service import (
    SeriesDriftPersistenceService,
)
from narrare_core.series.schemas import Series
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_drift_repo import FakeSeriesDriftRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

if TYPE_CHECKING:
    from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftResponse


def make_series(owner: uuid.UUID) -> Series:
    return Series(id=uuid.uuid4(), user_id=owner, title="Chronicles")


def make_novel(series_id: uuid.UUID) -> Novel:
    return Novel(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Band 1", series_id=series_id)


def make_chapter(novel_id: uuid.UUID, content: str, position: int) -> Chapter:
    chapter = Chapter()
    chapter.id = uuid.uuid4()
    chapter.novel_id = novel_id
    chapter.title = f"Chapter {position}"
    chapter.content = content
    chapter.position = position
    return chapter


def make_consistency_response(
    series_id: uuid.UUID, novel_id: uuid.UUID
) -> SeriesConsistencyCheckResponse:
    return SeriesConsistencyCheckResponse(
        series_id=series_id,
        novel_id=novel_id,
        conflicts=[],
        summary="No contradictions found.",
        canon_entry_count=2,
        chapter_count=2,
    )


def make_persistence_service(
    *,
    series_repo: FakeSeriesRepository,
    novel_repo: FakeNovelRepository,
    chapter_repo: FakeChapterRepository,
    drift_repo: FakeSeriesDriftRepository,
    consistency_return: SeriesConsistencyCheckResponse | None = None,
    voice_return: AuthorVoiceDriftResponse | None = None,
) -> SeriesDriftPersistenceService:
    consistency = AsyncMock()
    consistency.check_novel.return_value = consistency_return
    voice = AsyncMock()
    voice.check.return_value = voice_return
    return SeriesDriftPersistenceService(
        consistency_service=consistency,
        voice_drift_service=voice,
        series_repo=series_repo,
        novel_repo=novel_repo,
        chapter_repo=chapter_repo,
        drift_repo=drift_repo,
    )


def seeded_drift_fakes(
    owner: uuid.UUID,
) -> tuple[
    FakeSeriesRepository,
    FakeNovelRepository,
    FakeChapterRepository,
    FakeSeriesDriftRepository,
    Series,
    Novel,
]:
    """Seed series + member novel; empty chapter/drift fakes for the caller."""
    series = make_series(owner)
    novel = make_novel(series.id)
    series_repo = FakeSeriesRepository()
    series_repo.seed(series)
    novel_repo = FakeNovelRepository()
    novel_repo.seed(novel)
    return (
        series_repo,
        novel_repo,
        FakeChapterRepository(),
        FakeSeriesDriftRepository(),
        series,
        novel,
    )
