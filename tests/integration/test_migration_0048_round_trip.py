# tests/integration/test_migration_0048_round_trip.py
"""Round-trip test for migration 0048 (PLAN-001 generation_requests.scenes).

Verifies against real PG: upgrading to head adds the nullable ``scenes``
JSONB column to ``generation_requests`` and a seeded scene snapshot
survives INSERT → SELECT intact (nested objects/lists round-trip through
JSONB). Downgrading to the parent revision drops the column — WITH its
data, lossy by design: the snapshot is ephemeral request-scoped stream
state (spec §8.2 "what you approved is what streams"), not durable user
content, and the plan mandates a symmetric drop. The row itself and every
other column MUST survive the round trip; re-upgrading restores the
column (scenes back to NULL — no crash, no row loss, no other-column
corruption).

DB-level helpers (engine / alembic / seed_user) come from
``_usage_record_test_support.py`` — same subprocess-alembic machinery as
the 0043/0044/0045/0046/0047 round trips (RULE-04).

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test``
and CI run it in a dedicated SERIAL phase — never concurrently.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING, Any

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

# Downgrading to the parent revision applies ONLY 0048's downgrade.
_PARENT_REVISION = "0047_scene_plans"

# One full scene (all fields) + one minimal scene (defaults exercised).
_SCENES: list[dict[str, object]] = [
    {
        "title": "The Warning",
        "pov_character_name": "John",
        "location_name": "Gatehouse",
        "present_characters": [{"name": "John", "goal": "warn the guard"}],
        "purpose": "Raise the stakes",
        "conflict": "The guard refuses to listen",
        "resolution": "John forces his way in",
        "beats": ["John arrives", "Guard refuses", "John breaks through"],
        "status": "in_progress",
    },
    {"title": "The Blockade", "status": "planned"},
]


async def _column_exists(conn: AsyncConnection, table: str, column: str) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns"
                    " WHERE table_name = :t AND column_name = :c)"
                ),
                {"t": table, "c": column},
            )
        ).scalar()
    )


async def _seed_generation_request(
    conn: AsyncConnection, user_id: _uuid.UUID, novel_id: _uuid.UUID, chapter_id: _uuid.UUID
) -> _uuid.UUID:
    """Insert user/novel/chapter + one generation_requests row with scenes."""
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
    request_id = _uuid.uuid4()
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO generation_requests (id, chapter_id, novel_id, user_id, "
            "status, mode, tone, scenes) "
            "VALUES (:id, :cid, :nid, :uid, 'pending', 'scene_by_scene', 'balanced', :scenes)"
        ).bindparams(bindparam("scenes", type_=PG_JSONB)),
        {"id": request_id, "cid": chapter_id, "nid": novel_id, "uid": user_id, "scenes": _SCENES},
    )
    return request_id


async def _delete_seed(conn: AsyncConnection, novel_id: _uuid.UUID) -> None:
    """Remove the seeded rows (novel deletion CASCADEs chapter + requests)."""
    await conn.execute(sqlalchemy.text("DELETE FROM novels WHERE id = :nid"), {"nid": novel_id})


async def _fetch_row(conn: AsyncConnection, request_id: _uuid.UUID) -> Any:
    return (
        await conn.execute(
            sqlalchemy.text(
                "SELECT status, mode, tone, scenes FROM generation_requests WHERE id = :rid"
            ),
            {"rid": request_id},
        )
    ).one_or_none()


async def _fetch_row_without_scenes(conn: AsyncConnection, request_id: _uuid.UUID) -> Any:
    """Fetch only the surviving columns (valid while scenes is dropped)."""
    return (
        await conn.execute(
            sqlalchemy.text("SELECT status, mode, tone FROM generation_requests WHERE id = :rid"),
            {"rid": request_id},
        )
    ).one_or_none()


@pytest.mark.schema_mutating
class TestMigration0048RoundTrip:
    """0048 round-trip safety against the shared test DB."""

    async def test_seed_scenes_then_downgrade_then_upgrade(self) -> None:
        """Scenes round-trip at head; downgrade drops column, row survives."""
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        chapter_id = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                request_id = await _seed_generation_request(conn, user_id, novel_id, chapter_id)
        finally:
            await eng.dispose()

        try:
            # 1. At head: the seeded snapshot survives INSERT → SELECT intact.
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert await _column_exists(conn, "generation_requests", "scenes"), (
                        "scenes column must exist at head"
                    )
                    row = await _fetch_row(conn, request_id)
                    assert row is not None, "seeded request row must exist at head"
                    assert row.scenes == _SCENES, "JSONB round-trip must preserve the snapshot"
            finally:
                await eng.dispose()

            # 2. Downgrade to the parent: the column is gone — WITH its data
            #    (symmetric drop; lossy for the ephemeral snapshot) — while
            #    the row and all other columns survive untouched.
            run_alembic("downgrade", _PARENT_REVISION)
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert not await _column_exists(conn, "generation_requests", "scenes"), (
                        "scenes column must be dropped after downgrade"
                    )
                    row = await _fetch_row_without_scenes(conn, request_id)
                    assert row is not None, "request row must survive the downgrade"
                    assert (row.status, row.mode, row.tone) == (
                        "pending",
                        "scene_by_scene",
                        "balanced",
                    ), "non-scenes columns must survive the downgrade untouched"
            finally:
                await eng.dispose()

            # 3. Re-upgrade: column restored; row intact; snapshot is gone
            #    (NULL) — the documented lossy semantics of a symmetric drop.
            run_alembic("upgrade", "head")
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert await _column_exists(conn, "generation_requests", "scenes"), (
                        "scenes column must exist again after re-upgrade"
                    )
                    row = await _fetch_row(conn, request_id)
                    assert row is not None, "request row must survive the round trip"
                    assert row.scenes is None, "snapshot data is not restorable after drop"
                    assert (row.status, row.mode, row.tone) == (
                        "pending",
                        "scene_by_scene",
                        "balanced",
                    ), "row must still be intact after re-upgrade"
            finally:
                await eng.dispose()
        finally:
            # Safety net: clean the seed (CASCADE removes chapter/requests)
            # and ALWAYS leave the shared test DB at head.
            eng = engine()
            try:
                async with eng.begin() as conn:
                    await _delete_seed(conn, novel_id)
            finally:
                await eng.dispose()
            run_alembic("upgrade", "head")
