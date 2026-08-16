"""Snapshot-read tests for SeriesDriftPersistenceService (C2 — design §5).

RULE-04 split (gate-forced): the store-on-run tests live in
``test_series_drift_persistence_service.py``; the shared builders/seam live
in ``_series_drift_persistence_test_helpers.py``. Test bodies are the
brief's, verbatim.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftRequest,
    AuthorVoiceDriftResponse,
)
from narrare_core.shared.errors import ForbiddenError
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_drift_repo import FakeSeriesDriftRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository
from tests.unit.api.series._series_drift_persistence_test_helpers import (
    make_chapter,
    make_consistency_response,
    make_novel,
    make_persistence_service,
    seeded_drift_fakes,
)


class TestGetSnapshot:
    async def test_no_record_returns_all_null_snapshot(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        chapter_repo.seed(make_chapter(novel.id, "Prose one.", 1))
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
        )

        snapshot = await service.get_snapshot(series.id, novel.id, owner)

        assert snapshot.generated_at is None
        assert snapshot.consistency is None
        assert snapshot.voice_drift is None
        assert snapshot.stale is False

    async def test_unchanged_texts_are_fresh(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        # One prose chapter + one whitespace-only chapter (excluded from the
        # fingerprint by the non-empty filter, like the consistency check).
        chapter_repo.seed(make_chapter(novel.id, "Prose one.", 1), make_chapter(novel.id, "   ", 2))
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=make_consistency_response(series.id, novel.id),
        )
        await service.check_and_store_consistency(series.id, novel.id, owner)

        snapshot = await service.get_snapshot(series.id, novel.id, owner)

        assert snapshot.stale is False
        assert snapshot.consistency is not None
        assert snapshot.consistency.summary == "No contradictions found."

    async def test_edited_texts_flip_stale(self) -> None:
        """Design §12 gate: the stale-flag flip."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        chapter = make_chapter(novel.id, "Original prose.", 1)
        chapter_repo.seed(chapter)
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=make_consistency_response(series.id, novel.id),
        )
        await service.check_and_store_consistency(series.id, novel.id, owner)

        assert (await service.get_snapshot(series.id, novel.id, owner)).stale is False

        chapter.content = "Edited prose."  # the band's texts changed

        assert (await service.get_snapshot(series.id, novel.id, owner)).stale is True

    async def test_unknown_series_raises_forbidden(self) -> None:
        service = make_persistence_service(
            series_repo=FakeSeriesRepository(),
            novel_repo=FakeNovelRepository(),
            chapter_repo=FakeChapterRepository(),
            drift_repo=FakeSeriesDriftRepository(),
        )

        with pytest.raises(ForbiddenError):
            await service.get_snapshot(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    async def test_foreign_series_raises_forbidden(self) -> None:
        owner, stranger = uuid.uuid4(), uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
        )

        with pytest.raises(ForbiddenError):
            await service.get_snapshot(series.id, novel.id, stranger)

    async def test_non_member_novel_raises_forbidden(self) -> None:
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, _ = seeded_drift_fakes(owner)
        outsider = make_novel(uuid.uuid4())  # belongs to another series
        novel_repo.seed(outsider)
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
        )

        with pytest.raises(ForbiddenError):
            await service.get_snapshot(series.id, outsider.id, owner)

    async def test_snapshot_sections_round_trip_through_the_document(self) -> None:
        """Both sections coexist in ONE document and deserialize back into
        the run-result models (the reuse-don't-reshape binding)."""
        owner = uuid.uuid4()
        series_repo, novel_repo, chapter_repo, drift_repo, series, novel = seeded_drift_fakes(owner)
        chapter_repo.seed(make_chapter(novel.id, "Prose.", 1))
        voice_response = AuthorVoiceDriftResponse.model_validate(
            {"novel_id": str(novel.id), "no_profile": {"reason": "no_stored_series_voice"}}
        )
        service = make_persistence_service(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            drift_repo=drift_repo,
            consistency_return=make_consistency_response(series.id, novel.id),
            voice_return=voice_response,
        )
        await service.check_and_store_consistency(series.id, novel.id, owner)
        await service.check_and_store_voice_drift(
            series.id, novel.id, owner, AuthorVoiceDriftRequest()
        )

        snapshot = await service.get_snapshot(series.id, novel.id, owner)

        assert snapshot.generated_at is not None
        assert snapshot.consistency is not None
        assert snapshot.voice_drift is not None
        assert snapshot.voice_drift.no_profile is not None
        assert snapshot.voice_drift.no_profile.reason == "no_stored_series_voice"
