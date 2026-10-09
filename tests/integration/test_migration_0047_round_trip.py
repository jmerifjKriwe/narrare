# tests/integration/test_migration_0047_round_trip.py
"""Round-trip test for migration 0047 (PLAN-001 scene_plans — ADR-096).

Verifies against real PG: upgrading to head creates ``scene_plans`` and
backfills ONE scene per old ``chapter_outlines.planned_beats`` entry
(``title→title``, ``description→purpose``, ``completed→complete|planned``,
list order → ``position``). Non-dict beats are skipped — the historical
beat shape "is not locked down across all creators" (spec §3.3 tolerance).
Downgrading to the parent revision drops the table (lossless —
``planned_beats`` still exists there); re-upgrading re-runs the backfill
from the surviving beats data.

DB-level helpers (engine / alembic / seed_user) come from
``_usage_record_test_support.py`` — same subprocess-alembic machinery as the
0043/0044/0045/0046 round trips (RULE-04).

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test``
and CI run it in a dedicated SERIAL phase — never concurrently.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy import bindparam
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

from tests.integration._usage_record_test_support import (
    engine,
    run_alembic,
    seed_user,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# Downgrading to the parent revision applies ONLY 0047's downgrade.
_PARENT_REVISION = "0046_writing_goals"

# Two dict beats (mapped) + one garbage entry (skipped) — the T2 seed spec.
_BEATS: list[object] = [
    {"title": "The Warning", "description": "John warns the guard.", "completed": True},
    {"title": "The Blockade", "description": "Mara blocks the gate.", "completed": False},
    "garbage-not-a-dict",
]


async def _table_exists(conn: AsyncConnection, table: str) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"
                ),
                {"t": table},
            )
        ).scalar()
    )


async def _seed_novel_chapter_outline(
    conn: AsyncConnection, user_id: _uuid.UUID, novel_id: _uuid.UUID, chapter_id: _uuid.UUID
) -> None:
    await seed_user(conn, user_id)
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO novels (id, user_id, title, author, genre, "
            "writing_language, tone, story_structure, logline, synopsis, is_demo) "
            "VALUES (:id, :uid, 'RT Novel', '', '', 'en', '', 'three_act', '', '', false)"
        ),
        {"id": novel_id, "uid": user_id},
    )
    await conn.execute(
        sqlalchemy.text("INSERT INTO chapters (id, novel_id, title) VALUES (:id, :nid, 'Ch 1')"),
        {"id": chapter_id, "nid": novel_id},
    )
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO chapter_outlines (id, chapter_id, stage_assignment, "
            "planned_beats, outline_notes) VALUES (:id, :cid, 'act-1', :beats, '')"
        ).bindparams(bindparam("beats", type_=PG_JSONB)),
        {"id": _uuid.uuid4(), "cid": chapter_id, "beats": _BEATS},
    )


async def _delete_seed(conn: AsyncConnection, novel_id: _uuid.UUID) -> None:
    """Remove the seeded rows (novel deletion CASCADEs chapter/outline/scenes)."""
    await conn.execute(sqlalchemy.text("DELETE FROM novels WHERE id = :nid"), {"nid": novel_id})


@pytest.mark.schema_mutating
class TestMigration0047RoundTrip:
    """0047 round-trip safety against the shared test DB."""

    async def test_seed_beats_then_downgrade_then_upgrade(self) -> None:
        """Backfill maps beats → scenes; downgrade drops; re-up re-backfills."""
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        chapter_id = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                await _seed_novel_chapter_outline(conn, user_id, novel_id, chapter_id)
        finally:
            await eng.dispose()

        try:
            # 1. Downgrade to the parent: the table is gone, beats survive.
            run_alembic("downgrade", _PARENT_REVISION)
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert not await _table_exists(conn, "scene_plans"), (
                        "scene_plans must be dropped after downgrade"
                    )
            finally:
                await eng.dispose()

            # 2. Re-upgrade: the backfill re-runs from the surviving beats.
            run_alembic("upgrade", "head")
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert await _table_exists(conn, "scene_plans"), (
                        "scene_plans must exist at head"
                    )
                    rows = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT position, title, purpose, status, chapter_id "
                                "FROM scene_plans WHERE chapter_id = :cid ORDER BY position"
                            ),
                            {"cid": chapter_id},
                        )
                    ).all()
                    # 2 scenes — the non-dict garbage beat is skipped.
                    assert len(rows) == 2, f"expected 2 backfilled scenes, got {rows!r}"
                    assert [r.position for r in rows] == [1, 2], "list order → position"
                    assert [r.title for r in rows] == ["The Warning", "The Blockade"]
                    assert [r.purpose for r in rows] == [
                        "John warns the guard.",
                        "Mara blocks the gate.",
                    ]
                    assert [r.status for r in rows] == ["complete", "planned"], (
                        "completed → complete, else planned"
                    )
                    assert all(r.chapter_id == chapter_id for r in rows)
            finally:
                await eng.dispose()
        finally:
            # Safety net: clean the seed (CASCADE removes chapter/outline/scenes)
            # and ALWAYS leave the shared test DB at head.
            eng = engine()
            try:
                async with eng.begin() as conn:
                    await _delete_seed(conn, novel_id)
            finally:
                await eng.dispose()
            run_alembic("upgrade", "head")
