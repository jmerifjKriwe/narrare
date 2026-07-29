"""Unit tests for ``SeriesService`` CRUD business logic (fake repository).

Exercises every ``SeriesServiceProtocol`` method: CRUD happy paths, the
``SeriesNotFoundError`` domain error, PATCH field filtering (Task 3.3
note), and ``novel_count`` computation via ``repo.list_novels``. No
database — uses ``FakeSeriesRepository``.

Status-transition enforcement (the adjacency matrix) is covered in the
sibling module ``test_service_transitions.py``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.series.schemas import (
    SeriesCreateRequest,
    SeriesResponse,
    SeriesSummary,
    SeriesUpdateRequest,
)
from narrare.series.service import SeriesNotFoundError, SeriesService
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


# ---------------------------------------------------------------------------
# create_series
# ---------------------------------------------------------------------------


class TestCreateSeries:
    async def test_returns_response_with_default_draft_status_and_zero_novels(
        self,
    ) -> None:
        """A minimal create defaults to draft status; novel_count is 0."""
        repo = FakeSeriesRepository()
        service = SeriesService(repo)

        result = await service.create_series(
            USER_ID,
            SeriesCreateRequest(title="My Reihe"),
        )

        assert isinstance(result, SeriesResponse)
        assert result.title == "My Reihe"
        assert result.status == "draft"
        assert result.novel_count == 0
        assert result.user_id == USER_ID

    async def test_forwards_all_metadata_fields_to_repository(self) -> None:
        """Every request field is passed through to repo.create."""
        repo = FakeSeriesRepository()
        service = SeriesService(repo)

        await service.create_series(
            USER_ID,
            SeriesCreateRequest(
                title="Epic",
                subtitle="A subtitle",
                description="A description",
                genre="fantasy",
                writing_language="de",
                planned_novel_count=7,
            ),
        )

        create_call = next(c for c in repo.calls if c.method == "create")
        assert create_call.kwargs["title"] == "Epic"
        assert create_call.kwargs["subtitle"] == "A subtitle"
        assert create_call.kwargs["planned_novel_count"] == 7

    async def test_explicit_non_draft_status_is_applied_as_initial_state(
        self,
    ) -> None:
        """An explicit status on create sets the initial state directly."""
        repo = FakeSeriesRepository()
        service = SeriesService(repo)

        result = await service.create_series(
            USER_ID,
            SeriesCreateRequest(title="Completed Reihe", status="completed"),
        )

        assert result.status == "completed"


# ---------------------------------------------------------------------------
# get_series
# ---------------------------------------------------------------------------


class TestGetSeries:
    async def test_returns_response_with_computed_novel_count(self) -> None:
        """get_series counts novels via repo.list_novels."""
        series = _make_core_series(status="active")
        repo = FakeSeriesRepository()
        repo.seed(series, novels=["novel-a", "novel-b"])
        service = SeriesService(repo)

        result = await service.get_series(series.id)

        assert isinstance(result, SeriesResponse)
        assert result.id == series.id
        assert result.status == "active"
        assert result.novel_count == 2

    async def test_raises_series_not_found_when_missing(self) -> None:
        repo = FakeSeriesRepository()
        service = SeriesService(repo)

        with pytest.raises(SeriesNotFoundError):
            await service.get_series(uuid4())


# ---------------------------------------------------------------------------
# list_series
# ---------------------------------------------------------------------------


class TestListSeries:
    async def test_returns_summaries_with_per_series_novel_counts(self) -> None:
        s1 = _make_core_series(title="One")
        s2 = _make_core_series(title="Two")
        repo = FakeSeriesRepository()
        repo.seed(s1, novels=["n1"])
        repo.seed(s2, novels=["n1", "n2", "n3"])
        service = SeriesService(repo)

        result = await service.list_series(USER_ID)

        assert len(result) == 2
        assert all(isinstance(r, SeriesSummary) for r in result)
        counts = {r.title: r.novel_count for r in result}
        assert counts == {"One": 1, "Two": 3}

    async def test_returns_empty_list_when_user_has_no_series(self) -> None:
        repo = FakeSeriesRepository()
        service = SeriesService(repo)

        assert await service.list_series(uuid4()) == []


# ---------------------------------------------------------------------------
# update_series (CRUD aspects — transitions in test_service_transitions.py)
# ---------------------------------------------------------------------------


class TestUpdateSeries:
    async def test_patches_known_metadata_fields(self) -> None:
        series = _make_core_series(title="Old", genre=None)
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        result = await service.update_series(
            series.id,
            SeriesUpdateRequest(title="New", genre="horror"),
        )

        assert result.title == "New"
        assert result.genre == "horror"

    async def test_forwards_only_set_fields_not_unset_defaults(self) -> None:
        """PATCH semantics: unset fields are NOT forwarded to repo.update."""
        series = _make_core_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        await service.update_series(series.id, SeriesUpdateRequest(title="New"))

        update_call = next(c for c in repo.calls if c.method == "update")
        # Only title was set — subtitle/genre/etc. must not appear as None.
        assert update_call.kwargs["title"] == "New"
        assert "subtitle" not in update_call.kwargs
        assert "genre" not in update_call.kwargs

    async def test_same_status_is_allowed_as_noop(self) -> None:
        """Patching status to its current value is a no-op, not a transition."""
        series = _make_core_series(status="active")
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        result = await service.update_series(series.id, SeriesUpdateRequest(status="active"))

        assert result.status == "active"

    async def test_raises_series_not_found_when_missing(self) -> None:
        repo = FakeSeriesRepository()
        service = SeriesService(repo)

        with pytest.raises(SeriesNotFoundError):
            await service.update_series(uuid4(), SeriesUpdateRequest(title="X"))


# ---------------------------------------------------------------------------
# delete_series
# ---------------------------------------------------------------------------


class TestDeleteSeries:
    async def test_deletes_existing_series(self) -> None:
        series = _make_core_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        await service.delete_series(series.id)

        assert repo.call_count("delete") == 1
        # Verify removal through the public API, not internal state.
        assert await repo.get(series.id) is None

    async def test_raises_series_not_found_when_missing(self) -> None:
        repo = FakeSeriesRepository()
        service = SeriesService(repo)

        with pytest.raises(SeriesNotFoundError):
            await service.delete_series(uuid4())


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class TestErrorTypes:
    def test_series_not_found_carries_series_id(self) -> None:
        sid = uuid4()
        err = SeriesNotFoundError(sid)

        assert err.series_id == sid
        assert isinstance(err.identifier, str)

    def test_invalid_status_transition_carries_current_and_target(self) -> None:
        from narrare.series.service import InvalidStatusTransitionError

        err = InvalidStatusTransitionError("draft", "completed")

        assert err.current_status == "draft"
        assert err.target_status == "completed"
