"""Integration tests for migration 0037 — Series Foundation schema.

Verifies the migrated Postgres schema (Spec 1, Slice 1, Task 1.5) by
introspecting ``information_schema`` / ``pg_catalog``. The integration
conftest runs ``alembic upgrade head`` once per session (RULE-14: no
``create_all()``), so by the time these tests execute, migration 0037 has
already applied. Each test uses the rolled-back ``db_session`` fixture; all
queries here are read-only SELECTs against catalog tables, so they are safe
inside the per-test transaction.

These tests assert structure, not behaviour:
- ``series`` + ``series_settings`` tables exist with the expected columns.
- ``novels`` gained ``series_id`` / ``series_position`` / ``subtitle``.
- ``kb_entries`` gained ``series_id`` / ``base_entry_id`` and ``novel_id``
  became nullable (NULL = Series-Canon entry).
- The two PARTIAL unique indexes, the scope-invariant CHECK, the series
  status CHECK, and the novels ``(series_id, series_position)`` unique all
  exist with the right shape.

If no test Postgres is available, ``check_db_available`` (conftest) skips
the whole integration suite; CI runs these against a real DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Catalog introspection helpers (read-only)
# ---------------------------------------------------------------------------


async def _table_exists(db_session: AsyncSession, table_name: str) -> bool:
    """Return True iff ``table_name`` exists on the search_path."""
    result = await db_session.execute(
        sqlalchemy.text("SELECT to_regclass(:t) IS NOT NULL"),
        {"t": table_name},
    )
    return bool(result.scalar())


async def _column_exists(db_session: AsyncSession, table_name: str, column_name: str) -> bool:
    """Return True iff the column exists in the current schema's table."""
    result = await db_session.execute(
        sqlalchemy.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.one_or_none() is not None


async def _column_nullable(db_session: AsyncSession, table_name: str, column_name: str) -> bool:
    """Return True iff the column exists and is nullable (IS_NULLABLE = 'YES')."""
    result = await db_session.execute(
        sqlalchemy.text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = :t AND column_name = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    row = result.one_or_none()
    return row is not None and row[0] == "YES"


async def _index_def(db_session: AsyncSession, index_name: str) -> str | None:
    """Return the full ``CREATE INDEX`` DDL for ``index_name``, or None."""
    result = await db_session.execute(
        sqlalchemy.text("SELECT indexdef FROM pg_indexes WHERE indexname = :n"),
        {"n": index_name},
    )
    row = result.one_or_none()
    return str(row[0]) if row is not None else None


async def _constraint_type(db_session: AsyncSession, constraint_name: str) -> str | None:
    """Return the pg_constraint ``contype`` char, or None if absent.

    ``c`` = CHECK, ``u`` = UNIQUE, ``p`` = PRIMARY KEY, ``f`` = FOREIGN KEY.

    pg_catalog's ``contype`` is a single-byte ``"char"`` which asyncpg returns
    as ``bytes`` (e.g. ``b'c'``); decode to ``str`` for a clean comparison.
    """
    result = await db_session.execute(
        sqlalchemy.text("SELECT contype FROM pg_constraint WHERE conname = :n"),
        {"n": constraint_name},
    )
    row = result.one_or_none()
    if row is None:
        return None
    value = row[0]
    if isinstance(value, (bytes, bytearray)):
        return value.decode()
    return str(value)


# ---------------------------------------------------------------------------
# 1. series + series_settings tables
# ---------------------------------------------------------------------------


class TestSeriesTables:
    """The two new tables exist with the expected shape."""

    async def test_series_table_exists(self, db_session: AsyncSession) -> None:
        assert await _table_exists(db_session, "series")

    async def test_series_has_expected_columns(self, db_session: AsyncSession) -> None:
        for col in (
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
        ):
            assert await _column_exists(db_session, "series", col), f"series.{col} missing"

    async def test_series_required_columns_not_null(self, db_session: AsyncSession) -> None:
        for col in ("user_id", "title", "status", "created_at", "updated_at"):
            assert not await _column_nullable(db_session, "series", col), (
                f"series.{col} should be NOT NULL"
            )

    async def test_series_user_id_indexed(self, db_session: AsyncSession) -> None:
        assert await _index_def(db_session, "ix_series_user_id") is not None

    async def test_series_settings_table_exists(self, db_session: AsyncSession) -> None:
        assert await _table_exists(db_session, "series_settings")

    async def test_series_settings_has_expected_columns(self, db_session: AsyncSession) -> None:
        for col in ("id", "series_id", "author_voice", "created_at", "updated_at"):
            assert await _column_exists(db_session, "series_settings", col), (
                f"series_settings.{col} missing"
            )

    async def test_series_settings_author_voice_nullable(self, db_session: AsyncSession) -> None:
        # Spec 1: author_voice is present but empty/nullable (Spec 3 fills it).
        assert await _column_nullable(db_session, "series_settings", "author_voice")


# ---------------------------------------------------------------------------
# 2. novels: series membership columns
# ---------------------------------------------------------------------------


class TestNovelsColumns:
    """Novel gains optional series membership."""

    async def test_novels_has_series_columns(self, db_session: AsyncSession) -> None:
        assert await _column_exists(db_session, "novels", "series_id")
        assert await _column_exists(db_session, "novels", "series_position")
        assert await _column_exists(db_session, "novels", "subtitle")

    async def test_novels_series_columns_nullable(self, db_session: AsyncSession) -> None:
        # NULL series_id = standalone novel; all three are optional.
        assert await _column_nullable(db_session, "novels", "series_id")
        assert await _column_nullable(db_session, "novels", "series_position")
        assert await _column_nullable(db_session, "novels", "subtitle")

    async def test_novels_series_id_indexed(self, db_session: AsyncSession) -> None:
        assert await _index_def(db_session, "ix_novels_series_id") is not None

    async def test_novels_series_position_unique_constraint(self, db_session: AsyncSession) -> None:
        # uq_novels_series_position on (series_id, series_position).
        assert await _constraint_type(db_session, "uq_novels_series_position") == "u"


# ---------------------------------------------------------------------------
# 3. kb_entries: scope discriminator columns
# ---------------------------------------------------------------------------


class TestKbEntriesColumns:
    """KBEntry gains series scope; novel_id becomes nullable."""

    async def test_kb_entries_has_scope_columns(self, db_session: AsyncSession) -> None:
        assert await _column_exists(db_session, "kb_entries", "series_id")
        assert await _column_exists(db_session, "kb_entries", "base_entry_id")

    async def test_kb_entries_scope_columns_nullable(self, db_session: AsyncSession) -> None:
        assert await _column_nullable(db_session, "kb_entries", "series_id")
        assert await _column_nullable(db_session, "kb_entries", "base_entry_id")

    async def test_kb_entries_novel_id_is_nullable(self, db_session: AsyncSession) -> None:
        # Critical: novel_id must be nullable so Series-Canon entries can exist.
        assert await _column_nullable(db_session, "kb_entries", "novel_id")

    async def test_kb_entries_scope_columns_indexed(self, db_session: AsyncSession) -> None:
        assert await _index_def(db_session, "ix_kb_entries_series_id") is not None
        assert await _index_def(db_session, "ix_kb_entries_base_entry_id") is not None

    async def test_old_novel_slug_unique_constraint_dropped(self, db_session: AsyncSession) -> None:
        # Replaced by the partial unique indexes (TestKbEntriesPartialIndexes).
        assert await _constraint_type(db_session, "uq_kb_entries_novel_slug") is None


# ---------------------------------------------------------------------------
# 4. Partial unique indexes (Canon per series + Overlay per novel)
# ---------------------------------------------------------------------------


class TestKbEntriesPartialIndexes:
    """The two partial unique indexes replacing the old (novel_id, slug) unique."""

    async def test_canon_per_series_partial_unique(self, db_session: AsyncSession) -> None:
        indexdef = await _index_def(db_session, "uq_kb_canon_per_series")
        assert indexdef is not None, "uq_kb_canon_per_series index missing"
        upper = indexdef.upper()
        assert "UNIQUE" in upper, "canon index must be UNIQUE"
        assert "NOVEL_ID IS NULL" in upper, "canon index must be partial (novel_id IS NULL)"
        assert "SERIES_ID" in upper and "SLUG" in upper

    async def test_overlay_per_novel_partial_unique(self, db_session: AsyncSession) -> None:
        indexdef = await _index_def(db_session, "uq_kb_overlay_per_novel")
        assert indexdef is not None, "uq_kb_overlay_per_novel index missing"
        upper = indexdef.upper()
        assert "UNIQUE" in upper, "overlay index must be UNIQUE"
        assert "NOVEL_ID IS NOT NULL" in upper, (
            "overlay index must be partial (novel_id IS NOT NULL)"
        )


# ---------------------------------------------------------------------------
# 5. CHECK constraints
# ---------------------------------------------------------------------------


class TestCheckConstraints:
    """DB-level CHECK constraints enforced by the migration."""

    async def test_series_status_check_exists(self, db_session: AsyncSession) -> None:
        assert await _constraint_type(db_session, "ck_series_status") == "c"

    async def test_kb_entries_scope_invariant_check_exists(self, db_session: AsyncSession) -> None:
        assert await _constraint_type(db_session, "ck_kb_entries_scope_invariant") == "c"


# Round-trip safety (upgrade -> seed Canon -> downgrade -> upgrade) lives in
# the sibling ``test_migration_0037_round_trip.py`` (RULE-04 400-line split).
