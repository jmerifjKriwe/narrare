"""Schema-level tests for KBEntry scope columns (Series Foundation Spec 1, Task 1.4).

These assert the *structure* of the ``KBEntry`` model table — that the scope
discriminator columns exist and are nullable, that ``novel_id`` became
nullable (so Series-Canon entries can exist), and that the old
``(novel_id, slug)`` unique constraint was dropped (replaced by partial unique
indexes added in the Alembic migration 0036, Task 1.5).

They intentionally operate on ``KBEntry.__table__`` (Core-level introspection)
without a database, so they run in the fast unit layer — mirroring the
``Novel``/``Series`` introspection tests (Spec 1, Tasks 1.1/1.3).
"""

from __future__ import annotations

from sqlalchemy import Table

from narrare.kb.models import KBEntry


def test_kb_entry_has_series_id_column() -> None:
    """``series_id`` is a nullable FK to ``series.id`` (Series-Canon scope)."""
    cols = {c.name: c for c in KBEntry.__table__.columns}
    assert "series_id" in cols
    assert cols["series_id"].nullable is True


def test_kb_entry_has_base_entry_id_column() -> None:
    """``base_entry_id`` is a nullable self-FK (Novel-Overlay → Series-Canon)."""
    cols = {c.name: c for c in KBEntry.__table__.columns}
    assert "base_entry_id" in cols
    assert cols["base_entry_id"].nullable is True


def test_kb_entry_novel_id_is_nullable() -> None:
    """Critical: novel_id must be nullable so Series-Canon entries can exist."""
    cols = {c.name: c for c in KBEntry.__table__.columns}
    assert cols["novel_id"].nullable is True


def test_kb_entry_old_unique_constraint_dropped() -> None:
    """Old unique constraint dropped; partial uniques arrive in migration 0036."""
    # ``__table__`` is typed as ``FromClause``; narrow to ``Table`` so
    # ``.constraints`` is visible to the type checker.
    table = KBEntry.__table__
    assert isinstance(table, Table)
    constr_names = {c.name for c in table.constraints}
    assert "uq_kb_entries_novel_slug" not in constr_names
