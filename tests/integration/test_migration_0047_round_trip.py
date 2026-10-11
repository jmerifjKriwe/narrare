# tests/integration/test_migration_0047_round_trip.py
"""Round-trip test for migration 0047 (PLAN-001 scene_plans — ADR-096).

Verifies against real PG: upgrading from the parent revision creates
``scene_plans`` and backfills ONE scene per old ``chapter_outlines``
beat entry (``title→title``, ``description→purpose``,
``completed→complete|planned``, list order → ``position``). Non-dict beats
are skipped — the historical beat shape "is not locked down across all
creators" (spec §3.3 tolerance).

The legacy beats column only exists BELOW 0049 (the final drop), so the
seed runs at the parent revision (0046): downgrade head → 0046, seed the
beats there, then upgrade to head — the backfill runs at 0047 and the
subsequent 0048/0049 steps leave the backfilled scenes in place.

DB-level helpers (engine / alembic / seed_user) come from
``_usage_record_test_support.py`` — same subprocess-alembic machinery as
the 0043-0049 round trips (RULE-04).

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

# Seeding happens at 0046 — the last revision where the legacy beats
# column still exists (it is dropped by 0049 at head).
_SEED_REVISION = "0046_writing_goals"

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

    async def test_seed_beats_at_parent_then_upgrade_backfills(self) -> None:
        """Beats seeded at 0046 are backfilled into scenes by the upgrade;
        head afterwards is the final 0049 state (legacy column dropped)."""
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        chapter_id = _uuid.uuid4()

        # 1. Downgrade to the seed revision: the scene table is gone and the
        #    legacy beats column exists again (0049's downgrade recreates it).
        run_alembic("downgrade", _SEED_REVISION)
        eng = engine()
        try:
            async with eng.begin() as conn:
                assert not await _table_exists(conn, "scene_plans"), (
                    "downgrade to the seed revision must drop scene_plans"
                )
        finally:
            await eng.dispose()

        # 2. Seed the legacy beats AT the seed revision.
        eng = engine()
        try:
            async with eng.begin() as conn:
                await _seed_novel_chapter_outline(conn, user_id, novel_id, chapter_id)
        finally:
            await eng.dispose()

        try:
            # 3. Upgrade to head: 0047 backfills the scenes, 0049 then drops
            #    the legacy column — the backfilled scenes survive both.
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
