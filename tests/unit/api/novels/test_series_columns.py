"""Unit tests for the Series-related columns added to ``Novel`` (Spec 1, Task 1.3).

These introspect the SQLAlchemy ``Novel.__table__`` metadata directly — no
database is needed. The migration that materialises these columns in Postgres
arrives separately in Task 1.5 (RULE-14: one batched Alembic file).

The schema-level tests below also verify that ``series_id`` is surfaced in the
Pydantic response schemas, closing the contract gap that previously hid the
column from the API layer (frontend ``useNovelSeries`` hook).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from narrare.novels.models import Novel
from narrare.novels.schemas import NovelResponse, NovelSummaryResponse
from tests.factories import make_novel


def test_novel_has_series_id_column() -> None:
    """``series_id`` is a nullable FK column indexed for series lookups."""
    cols = {c.name: c for c in Novel.__table__.columns}
    assert "series_id" in cols
    assert cols["series_id"].nullable is True


def test_novel_has_series_position_column() -> None:
    """``series_position`` is nullable (NULL for standalone novels)."""
    cols = {c.name: c for c in Novel.__table__.columns}
    assert "series_position" in cols
    assert cols["series_position"].nullable is True


def test_novel_has_subtitle_column() -> None:
    """``subtitle`` is a nullable per-novel subtitle."""
    cols = {c.name: c for c in Novel.__table__.columns}
    assert "subtitle" in cols
    assert cols["subtitle"].nullable is True


def _novel(**overrides: Any) -> Any:
    """Build a ``Novel`` with timestamps populated so schema validation succeeds."""
    now = datetime.now(UTC)
    return make_novel(created_at=now, updated_at=now, **overrides)


def test_novel_response_exposes_series_id_when_set() -> None:
    """``NovelResponse`` maps the ORM ``series_id`` to the API response."""
    series_id = uuid.uuid4()
    novel = _novel(series_id=series_id)

    response = NovelResponse.model_validate(novel)

    assert response.series_id == series_id


def test_novel_response_series_id_is_none_for_standalone_novel() -> None:
    """Standalone novels (no series membership) expose ``series_id=None``."""
    novel = _novel(series_id=None)

    response = NovelResponse.model_validate(novel)

    assert response.series_id is None


def test_novel_summary_response_exposes_series_id() -> None:
    """``NovelSummaryResponse`` (used by the series novels list) surfaces ``series_id``."""
    series_id = uuid.uuid4()
    novel = _novel(series_id=series_id)

    response = NovelSummaryResponse.model_validate(novel)

    assert response.series_id == series_id


def test_novel_summary_response_exposes_series_position() -> None:
    """``NovelSummaryResponse`` surfaces ``series_position`` for list views.

    The BändeList component renders each band's number from this field; previously
    it could only show a placeholder badge because the field was absent from the
    schema (Spec 1 cleanup, ADR-075).
    """
    series_id = uuid.uuid4()
    novel = _novel(series_id=series_id, series_position=2)

    response = NovelSummaryResponse.model_validate(novel)

    assert response.series_position == 2


def test_novel_summary_response_series_position_is_none_for_standalone() -> None:
    """Standalone novels expose ``series_position=None`` (no band number)."""
    novel = _novel(series_id=None, series_position=None)

    response = NovelSummaryResponse.model_validate(novel)

    assert response.series_position is None
