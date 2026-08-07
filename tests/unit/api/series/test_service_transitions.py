"""Unit tests for ``SeriesService`` status-transition enforcement.

Covers the ``_ALLOWED_TRANSITIONS`` adjacency matrix end-to-end: every
allowed forward/back move (draft→active, active→completed, …) succeeds,
every non-adjacent skip (draft→completed, completed→active) raises
``InvalidStatusTransitionError``, and a blocked transition leaves the
series unchanged (no ``repo.update`` call).

CRUD aspects are in the sibling ``test_service.py``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.series.schemas import SeriesUpdateRequest
from narrare.series.service import (
    InvalidStatusTransitionError,
    SeriesService,
)
from narrare_core.series.schemas import Series
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


class TestStatusTransitions:
    @pytest.mark.parametrize(
        ("current", "target"),
        [
            ("draft", "active"),
            ("active", "completed"),
            ("active", "draft"),
            ("completed", "draft"),
        ],
    )
    async def test_allows_adjacent_status_transition(self, current: str, target: str) -> None:
        """Adjacent moves defined in the matrix succeed."""
        series = _make_core_series(status=current)
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        result = await service.update_series(
            series.id,
            USER_ID,
            SeriesUpdateRequest(status=target),  # type: ignore[arg-type]
        )

        assert result.status == target

    @pytest.mark.parametrize(
        ("current", "target"),
        [("draft", "completed"), ("completed", "active")],
    )
    async def test_rejects_non_adjacent_status_transition(self, current: str, target: str) -> None:
        """Skip moves not in the matrix raise InvalidStatusTransitionError."""
        series = _make_core_series(status=current)
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        with pytest.raises(InvalidStatusTransitionError):
            await service.update_series(
                series.id,
                USER_ID,
                SeriesUpdateRequest(status=target),  # type: ignore[arg-type]
            )

    async def test_rejected_transition_does_not_mutate_series(self) -> None:
        """A blocked transition leaves the series unchanged (no update call)."""
        series = _make_core_series(status="draft")
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        with pytest.raises(InvalidStatusTransitionError):
            await service.update_series(
                series.id,
                USER_ID,
                SeriesUpdateRequest(status="completed"),
            )

        assert repo.call_count("update") == 0
        # The series is unchanged — verify through the public API.
        unchanged = await repo.get(series.id)
        assert unchanged is not None
        assert unchanged.status == "draft"
