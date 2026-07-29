"""Unit tests for Series and SeriesSettings SQLAlchemy models."""

from __future__ import annotations

from narrare.series.models import Series as SeriesModel
from narrare.series.models import SeriesSettings as SeriesSettingsModel


def test_series_model_tablename() -> None:
    assert SeriesModel.__tablename__ == "series"


def test_series_settings_model_tablename() -> None:
    assert SeriesSettingsModel.__tablename__ == "series_settings"


def test_series_model_has_expected_columns() -> None:
    cols = {c.name for c in SeriesModel.__table__.columns}
    expected = {
        "id",
        "user_id",
        "title",
        "subtitle",
        "description",
        "genre",
        "writing_language",
        "status",
        "planned_novel_count",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols)


def test_series_settings_model_has_expected_columns() -> None:
    cols = {c.name for c in SeriesSettingsModel.__table__.columns}
    expected = {"id", "series_id", "author_voice", "created_at", "updated_at"}
    assert expected.issubset(cols)


def test_series_settings_series_id_unique() -> None:
    cols = {c.name: c for c in SeriesSettingsModel.__table__.columns}
    assert cols["series_id"].unique is True
