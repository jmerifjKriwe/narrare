"""Unit tests for the band-summary auto-trigger (Spec 2 Task 5).

Verifies that ``SeriesService.update_series`` enqueues band-summary generation
for every novel when the series status transitions to ``completed``, and does
NOT enqueue on other transitions. Uses a recording fake enqueuer injected via
the constructor (RULE-07 DI).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare.series.schemas import SeriesUpdateRequest
from narrare.series.service import SeriesService
from narrare_core.series.schemas import NovelRow, Series
from tests.fakes.fake_series_repo import FakeSeriesRepository

USER_ID = uuid4()


def _make_core_series(**overrides: object) -> Series:
    """Build a Core ``Series`` instance with sensible defaults."""
    defaults: dict[str, object] = {
        "id": uuid4(),
        "user_id": USER_ID,
        "title": "Test Series",
        "subtitle": None,
        "description": None,
        "genre": None,
        "writing_language": None,
        "status": "draft",
        "planned_novel_count": None,
    }
    defaults.update(overrides)
    return Series(**defaults)  # type: ignore[arg-type]


def _make_novel_row(series_id: UUID) -> NovelRow:
    """A minimal ``NovelRow`` for seeding the fake repo's novel list."""
    return NovelRow(
        id=uuid4(),
        user_id=USER_ID,
        series_id=series_id,
        series_position=1,
        title="A Novel",
    )


class _RecordingEnqueuer:
    """Fake ``BandSummaryEnqueuer`` that records every call + never fails."""

    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def __call__(self, novel_id: UUID) -> None:
        self.enqueued.append(novel_id)


class TestBandSummaryAutoTrigger:
    async def test_enqueues_for_each_novel_on_status_to_completed(self) -> None:
        """active→completed enqueues one task per novel in the series."""
        series = _make_core_series(status="active")
        novel_a = _make_novel_row(series.id)
        novel_b = _make_novel_row(series.id)
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[novel_a, novel_b])
        enqueuer = _RecordingEnqueuer()
        service = SeriesService(repo, enqueue_band_summary=enqueuer)

        await service.update_series(
            series.id,
            USER_ID,
            SeriesUpdateRequest(status="completed"),  # type: ignore[arg-type]
        )

        assert set(enqueuer.enqueued) == {novel_a.id, novel_b.id}
        assert len(enqueuer.enqueued) == 2

    async def test_does_not_enqueue_on_other_transitions(self) -> None:
        """draft→active must NOT trigger band-summary generation."""
        series = _make_core_series(status="draft")
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[_make_novel_row(series.id)])
        enqueuer = _RecordingEnqueuer()
        service = SeriesService(repo, enqueue_band_summary=enqueuer)

        await service.update_series(
            series.id,
            USER_ID,
            SeriesUpdateRequest(status="active"),  # type: ignore[arg-type]
        )

        assert enqueuer.enqueued == []

    async def test_does_not_enqueue_when_already_completed(self) -> None:
        """Setting status to its current value (completed→completed) is a no-op."""
        series = _make_core_series(status="completed")
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[_make_novel_row(series.id)])
        enqueuer = _RecordingEnqueuer()
        service = SeriesService(repo, enqueue_band_summary=enqueuer)

        await service.update_series(
            series.id,
            USER_ID,
            SeriesUpdateRequest(status="completed"),  # type: ignore[arg-type]
        )

        assert enqueuer.enqueued == []

    async def test_does_not_enqueue_when_no_enqueuer_injected(self) -> None:
        """Backward compat: ``SeriesService(repo)`` without enqueuer = no-op."""
        series = _make_core_series(status="active")
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[_make_novel_row(series.id)])
        service = SeriesService(repo)  # no enqueue_band_summary

        # Must not raise — backward compatibility with existing callers.
        result = await service.update_series(
            series.id,
            USER_ID,
            SeriesUpdateRequest(status="completed"),  # type: ignore[arg-type]
        )

        assert result.status == "completed"

    async def test_does_not_enqueue_when_series_has_no_novels(self) -> None:
        """A completed series with zero novels enqueues nothing."""
        series = _make_core_series(status="active")
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[])
        enqueuer = _RecordingEnqueuer()
        service = SeriesService(repo, enqueue_band_summary=enqueuer)

        await service.update_series(
            series.id,
            USER_ID,
            SeriesUpdateRequest(status="completed"),  # type: ignore[arg-type]
        )

        assert enqueuer.enqueued == []

    async def test_non_status_update_does_not_enqueue(self) -> None:
        """A PATCH that changes only the title must not trigger enqueuing."""
        series = _make_core_series(status="active")
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[_make_novel_row(series.id)])
        enqueuer = _RecordingEnqueuer()
        service = SeriesService(repo, enqueue_band_summary=enqueuer)

        await service.update_series(
            series.id,
            USER_ID,
            SeriesUpdateRequest(title="New Title"),  # type: ignore[arg-type]
        )

        assert enqueuer.enqueued == []

    @pytest.mark.parametrize(
        ("current", "target"),
        [("draft", "completed"), ("completed", "active")],
    )
    async def test_invalid_transition_does_not_enqueue(self, current: str, target: str) -> None:
        """A blocked transition raises before any enqueue can happen."""
        series = _make_core_series(status=current)
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[_make_novel_row(series.id)])
        enqueuer = _RecordingEnqueuer()
        service = SeriesService(repo, enqueue_band_summary=enqueuer)

        from narrare.series.service import InvalidStatusTransitionError

        with pytest.raises(InvalidStatusTransitionError):
            await service.update_series(
                series.id,
                USER_ID,
                SeriesUpdateRequest(status=target),  # type: ignore[arg-type]
            )

        assert enqueuer.enqueued == []
