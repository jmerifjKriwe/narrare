# tests/integration/test_migration_0046_round_trip.py
"""Round-trip test for migration 0046 (STATS-001 writing goals — ADR-095).

Verifies against real PG: at head, the ``project_settings`` schema matches
the model metadata exactly (RULE-14 parity — full column set + nullability,
stronger than a single-column probe because this migration EXTENDS a table
built by 0005..0045). A settings row inserted without ``writing_goals``
reads NULL (no goal); the v1 JSONB shape ``{"target_words": int | null}``
round-trips both ways. Downgrading to 0045 drops the column WITH its values
(goals are re-enterable settings — same argument as 0044's budget columns);
re-upgrading restores it, the surviving row reading NULL again.

DB-level helpers (engine / alembic / seed_user) come from
``_usage_record_test_support.py`` — same machinery as the 0043/0044/0045
round trips (RULE-04).

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test``
and CI run it in a dedicated SERIAL phase — never concurrently.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

import pytest
import sqlalchemy

from narrare.settings.models import ProjectSettings
from tests.integration._usage_record_test_support import (
    engine,
    run_alembic,
    seed_user,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# Downgrading to the parent revision applies ONLY 0046's downgrade.
_PARENT_REVISION = "0045_writing_activity_events"


async def _column_exists(conn: AsyncConnection, column: str) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'project_settings' AND column_name = :col)"
                ),
                {"col": column},
            )
        ).scalar()
    )


async def _db_columns(conn: AsyncConnection) -> dict[str, bool]:
    """Live column → nullable map for project_settings, as migrations built it."""
    rows = await conn.execute(
        sqlalchemy.text(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'project_settings'"
        )
    )
    return {name: nullable == "YES" for name, nullable in rows.all()}


async def _seed_novel_and_settings(
    conn: AsyncConnection, user_id: _uuid.UUID, novel_id: _uuid.UUID
) -> None:
    await seed_user(conn, user_id)
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO novels (id, user_id, title, author, genre, "
            "writing_language, tone, story_structure, logline, synopsis, is_demo) "
            "VALUES (:id, :uid, 'RT Novel', '', '', 'en', '', 'three_act', "
            "'', '', false)"
        ),
        {"id": novel_id, "uid": user_id},
    )
    # Omit writing_goals entirely — the pre-goal row shape.
    await conn.execute(
        sqlalchemy.text("INSERT INTO project_settings (novel_id) VALUES (:nid)"),
        {"nid": novel_id},
    )


@pytest.mark.schema_mutating
class TestMigration0046RoundTrip:
    """0046 round-trip safety against the shared test DB."""

    async def test_seed_then_downgrade_then_upgrade(self) -> None:
        """Parity + JSONB shape hold at head; downgrade drops; up restores NULL."""
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                await _seed_novel_and_settings(conn, user_id, novel_id)

                # A row that never had a goal reads NULL — no goal to report.
                row = (
                    await conn.execute(
                        sqlalchemy.text(
                            "SELECT writing_goals FROM project_settings WHERE novel_id = :nid"
                        ),
                        {"nid": novel_id},
                    )
                ).one()
                assert row[0] is None, "no goal until the user sets one"

                # RULE-14 parity: the migrations-built column set + nullability
                # must match the model metadata exactly — no drift either way.
                model_cols = {c.name: c.nullable for c in ProjectSettings.__table__.columns}
                assert await _db_columns(conn) == model_cols

                # V1 JSONB shape round-trips (set).
                await conn.execute(
                    sqlalchemy.text(
                        "UPDATE project_settings SET writing_goals = "
                        "'{\"target_words\": 50000}'::jsonb WHERE novel_id = :nid"
                    ),
                    {"nid": novel_id},
                )
                row = (
                    await conn.execute(
                        sqlalchemy.text(
                            "SELECT writing_goals FROM project_settings WHERE novel_id = :nid"
                        ),
                        {"nid": novel_id},
                    )
                ).one()
                assert row[0] == {"target_words": 50000}

                # Explicit unset shape round-trips too ({"target_words": null}).
                await conn.execute(
                    sqlalchemy.text(
                        "UPDATE project_settings SET writing_goals = "
                        "'{\"target_words\": null}'::jsonb WHERE novel_id = :nid"
                    ),
                    {"nid": novel_id},
                )
                row = (
                    await conn.execute(
                        sqlalchemy.text(
                            "SELECT writing_goals FROM project_settings WHERE novel_id = :nid"
                        ),
                        {"nid": novel_id},
                    )
                ).one()
                assert row[0] == {"target_words": None}
        finally:
            await eng.dispose()

        # Non-vacuousness guard: the seeded settings row COMMITTED and
        # survives the downgrade (only the COLUMN is dropped).
        try:
            run_alembic("downgrade", _PARENT_REVISION)
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert not await _column_exists(conn, "writing_goals"), (
                        "column must be gone after downgrade"
                    )
                    row = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT novel_id FROM project_settings WHERE novel_id = :nid"
                            ),
                            {"nid": novel_id},
                        )
                    ).one_or_none()
                    assert row is not None, "the settings row itself must survive"
            finally:
                await eng.dispose()

            run_alembic("upgrade", "head")
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert await _column_exists(conn, "writing_goals"), "column must exist at head"
                    row = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT writing_goals FROM project_settings WHERE novel_id = :nid"
                            ),
                            {"nid": novel_id},
                        )
                    ).one()
                    assert row[0] is None, "restored column reads NULL (dropped value)"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            run_alembic("upgrade", "head")
