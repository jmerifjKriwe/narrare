"""Unit tests for the Series-related columns added to ``Novel`` (Spec 1, Task 1.3).

These introspect the SQLAlchemy ``Novel.__table__`` metadata directly — no
database is needed. The migration that materialises these columns in Postgres
arrives separately in Task 1.5 (RULE-14: one batched Alembic file).
"""

from __future__ import annotations

from narrare.novels.models import Novel


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
