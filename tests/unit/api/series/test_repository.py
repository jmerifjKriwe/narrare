"""Unit tests for ``SeriesRepository`` query wiring (fake session).

The repository is a thin SQLAlchemy wrapper over Series + SeriesSettings +
novels-in-series (contracts: ``SeriesRepositoryProtocol``). These tests
exercise each method's query/return path and the create/update/delete
bookkeeping (flush+refresh, setattr loop, session.delete, 1:1 settings
invariant) without a real database — mirroring
``tests/unit/api/novels/test_novel_repository.py``.

Returns Core Pydantic types (``narrare_core.series``), so the converters are
covered transitively through every method that returns a Series/Settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

from narrare.series.models import Series as SeriesModel
from narrare.series.models import SeriesSettings as SeriesSettingsModel
from narrare.series.repository import SeriesRepository
from narrare_core.series.schemas import Series, SeriesSettings
from tests.factories import make_novel
from tests.fakes.fake_db_session import FakeDbSession, FakeResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _apply_python_defaults(model: object) -> None:
    """Apply scalar ``default=`` column values to a model instance.

    A real SQLAlchemy flush applies Python-side defaults before INSERT; the
    shared ``FakeDbSession.flush`` is a no-op counter. ``create`` returns a
    Core ``Series`` whose ``status`` field is non-optional, so this faithful
    flush step populates ``status='draft'``. Only *scalar* defaults are
    applied here: callable defaults (e.g. ``id`` via ``uuid4``) are invoked
    by SQLAlchemy with a execution-context argument we cannot reproduce, and
    are unneeded anyway — ``create`` generates the id itself so the 1:1
    settings row can reference it pre-flush. Server-side defaults
    (``created_at``) are intentionally left to the real DB.
    """
    from typing import Any

    from sqlalchemy.orm.attributes import set_attribute

    # ``__table__.columns`` introspection is untyped in SQLAlchemy stubs, so
    # the model is treated as ``Any`` here (production code never touches
    # this path — ``create`` generates the id itself).
    obj: Any = model
    for column in obj.__table__.columns:
        default = column.default
        if default is None:
            continue
        arg = default.arg
        if callable(arg):
            continue
        key = column.key
        if getattr(obj, key, None) is not None:
            continue
        set_attribute(obj, key, arg)


class _DefaultingSession(FakeDbSession):
    """FakeDbSession whose flush applies Python-side column defaults."""

    async def flush(self) -> None:
        for entity in self.added:
            _apply_python_defaults(entity)
        await super().flush()


def _make_series(**overrides: object) -> SeriesModel:
    """Build a Series ORM instance valid for Core conversion (status set)."""
    from sqlalchemy.orm.attributes import set_attribute

    model = SeriesModel()
    attrs: dict[str, object] = {
        "id": overrides.pop("id", uuid4()),
        "user_id": overrides.pop("user_id", uuid4()),
        "title": overrides.pop("title", "Test Series"),
        "status": overrides.pop("status", "draft"),
        **overrides,
    }
    for key, value in attrs.items():
        set_attribute(model, key, value)
    return model


def _make_settings(**overrides: object) -> SeriesSettingsModel:
    """Build a SeriesSettings ORM instance valid for Core conversion."""
    from sqlalchemy.orm.attributes import set_attribute

    model = SeriesSettingsModel()
    attrs: dict[str, object] = {
        "series_id": overrides.pop("series_id", uuid4()),
        "author_voice": overrides.pop("author_voice", None),
        # context_window_size has a column default of 3, but the Python-side
        # default is only applied at flush/insert — in the unit-test path (no
        # DB) the attribute reads as None, which the Core SeriesSettings schema
        # (non-nullable int) rejects. Set it explicitly so the mock ORM is
        # valid without depending on DB behaviour.
        "context_window_size": overrides.pop("context_window_size", 3),
        **overrides,
    }
    for key, value in attrs.items():
        set_attribute(model, key, value)
    return model


class TestSeriesRepositoryCreate:
    async def test_create_inserts_series_and_settings_and_returns_core(self) -> None:
        """create() adds Series + empty SeriesSettings (1:1) and returns Core."""
        session = _DefaultingSession()
        repo = SeriesRepository(cast("AsyncSession", session))

        user_id = uuid4()
        result = await repo.create(
            user_id=user_id,
            title="My Reihe",
            subtitle="Band Eins",
            description="A fantasy series.",
            genre="fantasy",
            writing_language="de",
            planned_novel_count=5,
        )

        # Returns the Core Pydantic type with the provided fields + default status.
        assert isinstance(result, Series)
        assert result.title == "My Reihe"
        assert result.subtitle == "Band Eins"
        assert result.description == "A fantasy series."
        assert result.genre == "fantasy"
        assert result.writing_language == "de"
        assert result.planned_novel_count == 5
        assert result.user_id == user_id
        assert result.status == "draft"

        # 1:1 invariant: a Series and an empty SeriesSettings were both added.
        assert len(session.added) == 2
        series_model, settings_model = session.added
        assert isinstance(series_model, SeriesModel)
        assert isinstance(settings_model, SeriesSettingsModel)
        assert settings_model.series_id == series_model.id
        assert settings_model.author_voice is None

        # Flushed once + the Series was refreshed (server-defaults load path).
        assert session.flush_count == 1
        assert series_model in session.refreshed


class TestSeriesRepositoryGet:
    async def test_get_returns_core_series_when_found(self) -> None:
        model = _make_series(title="Found")
        session = FakeDbSession([FakeResult(value=model)])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.get(model.id)

        assert isinstance(result, Series)
        assert result.id == model.id
        assert result.title == "Found"
        assert result.status == "draft"

    async def test_get_returns_none_when_missing(self) -> None:
        session = FakeDbSession([FakeResult(value=None)])
        repo = SeriesRepository(cast("AsyncSession", session))

        assert await repo.get(uuid4()) is None


class TestSeriesRepositoryListForUser:
    async def test_list_for_user_returns_core_series_list(self) -> None:
        models = [_make_series(title="A"), _make_series(title="B")]
        session = FakeDbSession([FakeResult(scalars=models)])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.list_for_user(uuid4())

        assert len(result) == 2
        assert all(isinstance(r, Series) for r in result)
        assert [r.title for r in result] == ["A", "B"]

    async def test_list_for_user_returns_empty_when_none(self) -> None:
        session = FakeDbSession([FakeResult(scalars=[])])
        repo = SeriesRepository(cast("AsyncSession", session))

        assert await repo.list_for_user(uuid4()) == []


class TestSeriesRepositoryUpdate:
    async def test_update_patches_fields_and_returns_core(self) -> None:
        model = _make_series(title="Old", genre=None)
        session = FakeDbSession([FakeResult(value=model)])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.update(model.id, title="New", genre="horror")

        assert isinstance(result, Series)
        assert result.title == "New"
        assert result.genre == "horror"
        # The ORM instance was mutated in place.
        assert model.title == "New"
        assert model.genre == "horror"
        assert session.flush_count == 1
        assert model in session.refreshed

    async def test_update_returns_none_when_missing(self) -> None:
        session = FakeDbSession([FakeResult(value=None)])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.update(uuid4(), title="X")

        assert result is None
        assert session.flush_count == 0


class TestSeriesRepositoryDelete:
    async def test_delete_removes_series_and_flushes(self) -> None:
        model = _make_series()
        session = FakeDbSession([FakeResult(value=model)])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.delete(model.id)

        assert result is True
        assert session.deleted == [model]
        assert session.flush_count == 1

    async def test_delete_returns_false_when_missing(self) -> None:
        session = FakeDbSession([FakeResult(value=None)])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.delete(uuid4())

        assert result is False
        assert session.deleted == []
        assert session.flush_count == 0


class TestSeriesRepositoryListNovels:
    async def test_list_novels_returns_novel_rows_ordered(self) -> None:
        """list_novels maps ORM rows → Core NovelRow value objects (I-A2)."""
        from narrare_core.series.schemas import NovelRow

        series_id = uuid4()
        n1 = make_novel(series_id=series_id, series_position=1, title="First")
        n2 = make_novel(series_id=series_id, series_position=2, title="Second")
        session = FakeDbSession([FakeResult(scalars=[n1, n2])])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.list_novels(series_id)

        assert all(isinstance(r, NovelRow) for r in result)
        assert [r.title for r in result] == ["First", "Second"]
        assert [r.series_position for r in result] == [1, 2]
        assert all(r.series_id == series_id for r in result)

    async def test_list_novels_returns_empty_when_none(self) -> None:
        session = FakeDbSession([FakeResult(scalars=[])])
        repo = SeriesRepository(cast("AsyncSession", session))

        assert await repo.list_novels(uuid4()) == []


class TestSeriesRepositoryReorderNovels:
    async def test_reorder_assigns_sequential_positions_in_list_order(self) -> None:
        """Positions follow the novel_ids order, not the DB load order."""
        series_id = uuid4()
        n1 = make_novel(series_id=series_id, series_position=3)
        n2 = make_novel(series_id=series_id, series_position=1)
        n3 = make_novel(series_id=series_id, series_position=2)
        session = FakeDbSession([FakeResult(scalars=[n1, n2, n3])])
        repo = SeriesRepository(cast("AsyncSession", session))

        await repo.reorder_novels(series_id, [n2.id, n3.id, n1.id])

        assert n2.series_position == 1
        assert n3.series_position == 2
        assert n1.series_position == 3
        assert session.flush_count == 1

    async def test_reorder_ignores_ids_not_in_series(self) -> None:
        """A novel_id not belonging to the series is silently skipped."""
        series_id = uuid4()
        n1 = make_novel(series_id=series_id, series_position=5)
        n2 = make_novel(series_id=series_id, series_position=9)
        session = FakeDbSession([FakeResult(scalars=[n1, n2])])
        repo = SeriesRepository(cast("AsyncSession", session))

        await repo.reorder_novels(series_id, [n1.id, uuid4()])

        assert n1.series_position == 1
        # n2 was not in the requested list → untouched.
        assert n2.series_position == 9


class TestSeriesRepositoryGetSettings:
    async def test_get_settings_returns_core_when_found(self) -> None:
        model = _make_settings(author_voice={"style": "spare"})
        session = FakeDbSession([FakeResult(value=model)])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.get_settings(model.series_id)

        assert isinstance(result, SeriesSettings)
        assert result.series_id == model.series_id
        assert result.author_voice == {"style": "spare"}

    async def test_get_settings_returns_none_when_missing(self) -> None:
        session = FakeDbSession([FakeResult(value=None)])
        repo = SeriesRepository(cast("AsyncSession", session))

        assert await repo.get_settings(uuid4()) is None


class TestSeriesRepositoryUpdateSettings:
    async def test_update_settings_patches_existing(self) -> None:
        model = _make_settings(author_voice=None)
        session = FakeDbSession([FakeResult(value=model)])
        repo = SeriesRepository(cast("AsyncSession", session))

        result = await repo.update_settings(model.series_id, {"author_voice": {"x": 1}})

        assert isinstance(result, SeriesSettings)
        assert result.author_voice == {"x": 1}
        assert model.author_voice == {"x": 1}
        assert session.flush_count == 1
        assert model in session.refreshed
        assert session.added == []  # no new row created

    async def test_update_settings_creates_row_when_missing(self) -> None:
        """No settings row → create-on-demand, then patch + return."""
        # _DefaultingSession applies the context_window_size Python-side
        # default (3) on flush — a plain FakeDbSession.flush is a no-op, so
        # the non-nullable Core field would otherwise read as None.
        session = _DefaultingSession([FakeResult(value=None)])
        repo = SeriesRepository(cast("AsyncSession", session))

        series_id = uuid4()
        result = await repo.update_settings(series_id, {"author_voice": {"y": 2}})

        assert isinstance(result, SeriesSettings)
        assert result.series_id == series_id
        assert result.author_voice == {"y": 2}
        # Exactly one new SeriesSettings row was added.
        assert len(session.added) == 1
        assert isinstance(session.added[0], SeriesSettingsModel)
        assert session.added[0].series_id == series_id
        assert session.flush_count == 1
