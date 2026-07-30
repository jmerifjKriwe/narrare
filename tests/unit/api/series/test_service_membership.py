"""Unit tests for ``SeriesService`` novels-in-series + settings methods.

Covers the router-facing surface added in Task 3.6 (``list_novels``,
``reorder_novels``, ``get_settings``, ``update_settings``): happy path +
``SeriesNotFoundError`` (404) when the series does not exist. Uses the
in-memory ``FakeSeriesRepository`` (ADR-030); CRUD/transition coverage is
in the sibling ``test_service.py`` / ``test_service_transitions.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from narrare.novels.schemas import NovelSummaryResponse
from narrare.series.schemas import SeriesSettingsUpdateRequest
from narrare.series.service import SeriesNotFoundError, SeriesService
from narrare_core.series.schemas import Series
from tests.factories import make_novel
from tests.fakes.fake_series_repo import FakeSeriesRepository

USER_ID = uuid4()


def _make_series(**overrides: object) -> Series:
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


class TestListNovels:
    async def test_returns_novels_as_summary_responses(self) -> None:
        series = _make_series()
        novel = make_novel(id=uuid4(), updated_at=datetime.now(UTC))
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[novel])
        service = SeriesService(repo)

        result = await service.list_novels(series.id)

        assert len(result) == 1
        assert isinstance(result[0], NovelSummaryResponse)
        assert result[0].title == novel.title

    async def test_unknown_series_raises_not_found(self) -> None:
        service = SeriesService(FakeSeriesRepository())

        with pytest.raises(SeriesNotFoundError):
            await service.list_novels(uuid4())


class TestReorderNovels:
    async def test_delegates_to_repository(self) -> None:
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)
        order = [uuid4(), uuid4()]

        await service.reorder_novels(series.id, order)

        assert repo.call_count("reorder_novels") == 1

    async def test_unknown_series_raises_not_found(self) -> None:
        service = SeriesService(FakeSeriesRepository())

        with pytest.raises(SeriesNotFoundError):
            await service.reorder_novels(uuid4(), [uuid4()])


class TestGetSettings:
    async def test_returns_stored_settings(self) -> None:
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        # Simulate a previously-saved author_voice.
        await repo.update_settings(series.id, {"author_voice": {"tone": "formal"}})
        service = SeriesService(repo)

        result = await service.get_settings(series.id)

        assert result.series_id == series.id
        assert result.author_voice == {"tone": "formal"}

    async def test_synthesises_default_when_no_row(self) -> None:
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        # Drop the settings row the seed created to exercise the default path.
        repo._settings.pop(series.id)  # pyright: ignore[reportPrivateUsage]
        service = SeriesService(repo)

        result = await service.get_settings(series.id)

        assert result.author_voice is None

    async def test_unknown_series_raises_not_found(self) -> None:
        service = SeriesService(FakeSeriesRepository())

        with pytest.raises(SeriesNotFoundError):
            await service.get_settings(uuid4())


class TestUpdateSettings:
    async def test_forwards_provided_fields_only(self) -> None:
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        result = await service.update_settings(
            series.id, SeriesSettingsUpdateRequest(author_voice={"tone": "wry"})
        )

        assert result.author_voice == {"tone": "wry"}

    async def test_unset_field_is_not_forwarded(self) -> None:
        """exclude_unset semantics: an absent author_voice does not clear it."""
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        await repo.update_settings(series.id, {"author_voice": {"tone": "wry"}})
        service = SeriesService(repo)

        result = await service.update_settings(series.id, SeriesSettingsUpdateRequest())

        assert result.author_voice == {"tone": "wry"}

    async def test_unknown_series_raises_not_found(self) -> None:
        service = SeriesService(FakeSeriesRepository())

        with pytest.raises(SeriesNotFoundError):
            await service.update_settings(
                uuid4(), SeriesSettingsUpdateRequest(author_voice={"tone": "x"})
            )
