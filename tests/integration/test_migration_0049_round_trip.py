# tests/integration/test_migration_0049_round_trip.py
"""Round-trip test for migration 0049 (PLAN-001 final drop — ADR-096).

Verifies against real PG: 0049 drops ``chapter_outlines.planned_beats`` (the
substrate since 0047 is ``scene_plans`` — zero readers remained after
T14/T15/T16). Downgrading to the parent revision (0048) recreates the column
(0013 shape: JSONB, server default ``'[]'::jsonb``) and REVERSE-MIGRATES
scenes → beats per spec §3.3 — one beat per scene, ordered by position:
``title→title``, ``purpose→description``, ``status=="complete"→completed``.

The reverse-migration is documented LOSSY (spec §3.3): scene-only fields
(conflict/resolution/per-scene beats/hybrid refs) have no beat equivalent.
They survive THIS round trip only because the ``scene_plans`` rows persist —
downgrading further (0047) would drop the table and lose them for good.

DB-level helpers (engine / alembic / seed_user) come from
``_usage_record_test_support.py`` — same subprocess-alembic machinery as the
0043-0048 round trips (RULE-04).

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

# Downgrading to the parent revision applies ONLY 0049's downgrade.
_PARENT_REVISION = "0048_generation_scenes"

# Two scenes — the first complete and carrying scene-only fields (the lossy
# side of the reverse-migration), the second merely planned.
_SCENES: list[dict[str, object]] = [
    {
        "position": 1,
        "title": "The Warning",
        "purpose": "John warns the guard.",
        "conflict": "The guard does not believe him.",
        "resolution": "He shows the sigil.",
        "beats": ["Guard post at dusk", "Sigil revealed"],
        "status": "complete",
    },
    {
        "position": 2,
        "title": "The Blockade",
        "purpose": "Mara blocks the gate.",
        "conflict": "",
        "resolution": "",
        "beats": [],
        "status": "planned",
    },
]


async def _column_exists(conn: AsyncConnection, table: str, column: str) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c)"
                ),
                {"t": table, "c": column},
            )
        ).scalar()
    )


async def _seed_novel_chapter_scenes(
    conn: AsyncConnection, user_id: _uuid.UUID, novel_id: _uuid.UUID, chapter_id: _uuid.UUID
) -> None:
    """Seed at HEAD: an outline row (the dropped column is NOT named) + scenes."""
    await seed_user(conn, user_id)
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO novels (id, user_id, title, author, genre, "
            "writing_language, tone, story_structure, logline, synopsis, is_demo) "
            "VALUES (:id, :uid, 'RT Novel 49', '', '', 'en', '', 'three_act', '', '', false)"
        ),
        {"id": novel_id, "uid": user_id},
    )
    await conn.execute(
        sqlalchemy.text("INSERT INTO chapters (id, novel_id, title) VALUES (:id, :nid, 'Ch 1')"),
        {"id": chapter_id, "nid": novel_id},
    )
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO chapter_outlines (id, chapter_id, stage_assignment, outline_notes) "
            "VALUES (:id, :cid, 'act-1', '')"
        ),
        {"id": _uuid.uuid4(), "cid": chapter_id},
    )
    for scene in _SCENES:
        await conn.execute(
            sqlalchemy.text(
                "INSERT INTO scene_plans (id, chapter_id, position, title, purpose, "
                "conflict, resolution, beats, status) "
                "VALUES (:id, :cid, :position, :title, :purpose, :conflict, :resolution, "
                ":beats, :status)"
            ).bindparams(bindparam("beats", type_=PG_JSONB)),
            {"id": _uuid.uuid4(), "cid": chapter_id, **scene},
        )


@pytest.mark.schema_mutating
class TestMigration0049RoundTrip:
    """0049 round-trip safety against the shared test DB."""

    async def test_seed_scenes_then_downgrade_then_upgrade(self) -> None:
        """Downgrade reverse-migrates scenes → beats; re-upgrade re-drops."""
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        chapter_id = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                await _seed_novel_chapter_scenes(conn, user_id, novel_id, chapter_id)
        finally:
            await eng.dispose()

        try:
            # 1. Downgrade to the parent: the column is back and carries the
            #    reverse-migrated beats (spec §3.3 mapping, positions 1..N).
            run_alembic("downgrade", _PARENT_REVISION)
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert await _column_exists(conn, "chapter_outlines", "planned_beats"), (
                        "downgrade must recreate the legacy beats column"
                    )
                    beats = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT planned_beats FROM chapter_outlines WHERE chapter_id = :cid"
                            ),
                            {"cid": chapter_id},
                        )
                    ).scalar_one()
                    assert beats == [
                        {
                            "title": "The Warning",
                            "description": "John warns the guard.",
                            "completed": True,
                        },
                        {
                            "title": "The Blockade",
                            "description": "Mara blocks the gate.",
                            "completed": False,
                        },
                    ], "scenes reverse-migrate to beats ordered by position (spec §3.3)"
            finally:
                await eng.dispose()

            # 2. Re-upgrade: the column is dropped again and the scene rows are
            #    untouched — title/purpose/status AND the scene-only fields
            #    (lossy on the beats side, spec §3.3) all survive on scenes.
            run_alembic("upgrade", "head")
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert not await _column_exists(conn, "chapter_outlines", "planned_beats"), (
                        "re-upgrade must drop the legacy beats column again"
                    )
                    rows = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT position, title, purpose, conflict, resolution, "
                                "beats, status FROM scene_plans WHERE chapter_id = :cid "
                                "ORDER BY position"
                            ),
                            {"cid": chapter_id},
                        )
                    ).all()
                    assert len(rows) == 2, f"expected the 2 seeded scenes, got {rows!r}"
                    assert [r.position for r in rows] == [1, 2]
                    assert [r.title for r in rows] == ["The Warning", "The Blockade"]
                    assert [r.purpose for r in rows] == [
                        "John warns the guard.",
                        "Mara blocks the gate.",
                    ]
                    assert [r.status for r in rows] == ["complete", "planned"]
                    # Scene-only fields (no beat equivalent — the documented
                    # loss) live ONLY here and survive because scene_plans
                    # rows are never touched by 0049.
                    assert rows[0].conflict == "The guard does not believe him."
                    assert rows[0].resolution == "He shows the sigil."
                    assert list(rows[0].beats) == ["Guard post at dusk", "Sigil revealed"]
            finally:
                await eng.dispose()
        finally:
            # Safety net: clean the seed (CASCADE removes chapter/outline/scenes)
            # and ALWAYS leave the shared test DB at head.
            eng = engine()
            try:
                async with eng.begin() as conn:
                    await conn.execute(
                        sqlalchemy.text("DELETE FROM novels WHERE id = :nid"), {"nid": novel_id}
                    )
            finally:
                await eng.dispose()
            run_alembic("upgrade", "head")
