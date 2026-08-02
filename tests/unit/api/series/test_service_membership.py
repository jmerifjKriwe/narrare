"""Unit tests for ``SeriesService`` novels-in-series + settings methods.

Covers the router-facing surface (``list_novels``, ``reorder_novels``,
``get_settings``, ``update_settings``): happy path + ``ForbiddenError`` (403,
anti-enumeration) when the series is missing/not owned. Uses the in-memory
``FakeSeriesRepository`` (ADR-030); CRUD/transition coverage is in the sibling
``test_service.py`` / ``test_service_transitions.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from narrare.series.schemas import SeriesSettingsUpdateRequest
from narrare.series.service import SeriesService
from narrare_core.series.schemas import NovelRow, Series
from narrare_core.shared.errors import ForbiddenError
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
    async def test_returns_novels_as_novel_rows(self) -> None:
        """list_novels returns Core ``NovelRow`` value objects (I-A2)."""
        series = _make_series()
        novel = make_novel(id=uuid4(), user_id=USER_ID, updated_at=datetime.now(UTC))
        repo = FakeSeriesRepository()
        repo.seed(series, novels=[novel])
        service = SeriesService(repo)

        result = await service.list_novels(series.id, USER_ID)

        assert len(result) == 1
        assert isinstance(result[0], NovelRow)
        assert result[0].title == novel.title

    async def test_unknown_series_raises_forbidden(self) -> None:
        """Anti-enumeration: a missing series surfaces as 403, not 404."""
        service = SeriesService(FakeSeriesRepository())

        with pytest.raises(ForbiddenError):
            await service.list_novels(uuid4(), USER_ID)

    async def test_not_owned_series_raises_forbidden(self) -> None:
        series = _make_series(user_id=uuid4())  # different owner
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        with pytest.raises(ForbiddenError):
            await service.list_novels(series.id, USER_ID)


class TestReorderNovels:
    async def test_delegates_to_repository(self) -> None:
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)
        order = [uuid4(), uuid4()]

        await service.reorder_novels(series.id, USER_ID, order)

        assert repo.call_count("reorder_novels") == 1

    async def test_unknown_series_raises_forbidden(self) -> None:
        service = SeriesService(FakeSeriesRepository())

        with pytest.raises(ForbiddenError):
            await service.reorder_novels(uuid4(), USER_ID, [uuid4()])


class TestGetSettings:
    async def test_returns_stored_settings(self) -> None:
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        # Simulate a previously-saved author_voice.
        await repo.update_settings(series.id, {"author_voice": {"tone": "formal"}})
        service = SeriesService(repo)

        result = await service.get_settings(series.id, USER_ID)

        assert result.series_id == series.id
        assert result.author_voice == {"tone": "formal"}

    async def test_synthesises_default_when_no_row(self) -> None:
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        # Drop the settings row the seed created to exercise the default path.
        repo._settings.pop(series.id)  # pyright: ignore[reportPrivateUsage]
        service = SeriesService(repo)

        result = await service.get_settings(series.id, USER_ID)

        assert result.author_voice is None

    async def test_unknown_series_raises_forbidden(self) -> None:
        service = SeriesService(FakeSeriesRepository())

        with pytest.raises(ForbiddenError):
            await service.get_settings(uuid4(), USER_ID)


class TestUpdateSettings:
    async def test_forwards_provided_fields_only(self) -> None:
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        service = SeriesService(repo)

        result = await service.update_settings(
            series.id, USER_ID, SeriesSettingsUpdateRequest(author_voice={"tone": "wry"})
        )

        assert result.author_voice == {"tone": "wry"}

    async def test_unset_field_is_not_forwarded(self) -> None:
        """exclude_unset semantics: an absent author_voice does not clear it."""
        series = _make_series()
        repo = FakeSeriesRepository()
        repo.seed(series)
        await repo.update_settings(series.id, {"author_voice": {"tone": "wry"}})
        service = SeriesService(repo)

        result = await service.update_settings(series.id, USER_ID, SeriesSettingsUpdateRequest())

        assert result.author_voice == {"tone": "wry"}

    async def test_unknown_series_raises_forbidden(self) -> None:
        service = SeriesService(FakeSeriesRepository())

        with pytest.raises(ForbiddenError):
            await service.update_settings(
                uuid4(), USER_ID, SeriesSettingsUpdateRequest(author_voice={"tone": "x"})
            )
