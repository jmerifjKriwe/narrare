# tests/integration/test_migration_0045_round_trip.py
"""Round-trip test for migration 0045 (STATS-001 writing stats — ADR-095).

Verifies against real PG: at head, the migration-created schema matches the
``WritingActivityEventRow`` model metadata (RULE-14 parity — exact column
set + nullability), signed ``delta_words`` accepts BOTH signs (deliberately
NO CHECK), ``created_at`` must be supplied by the recorder (NOT NULL, no
server default) and the FK contracts ADR-095 relies on are enforced by the
DB, not just the ORM — user ON DELETE RESTRICT, novel/chapter ON DELETE SET
NULL; both indices exist. Downgrading to 0044 drops the table with its rows
(writing telemetry is non-critical, derived data); re-upgrading recreates it
empty.

DB-level helpers (engine / alembic / seed_user) come from
``_usage_record_test_support.py`` — same machinery as the 0043/0044 round
trips (RULE-04).

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test``
and CI run it in a dedicated SERIAL phase — never concurrently.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy.exc import IntegrityError

from narrare.analytics.writing_models import WritingActivityEventRow
from tests.integration._usage_record_test_support import (
    JAN_1,
    engine,
    run_alembic,
    seed_user,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# Downgrading to the parent revision applies ONLY 0045's downgrade.
_PARENT_REVISION = "0044_budget_settings"

# The shared fixed seed timestamp doubles as the recorder's created_at.
_CREATED_AT = JAN_1


async def _table_exists(conn: AsyncConnection) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'writing_activity_events')"
                )
            )
        ).scalar()
    )


async def _index_exists(conn: AsyncConnection, name: str) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text("SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = :name)"),
                {"name": name},
            )
        ).scalar()
    )


async def _db_columns(conn: AsyncConnection) -> dict[str, bool]:
    """Live column → nullable map, as the migration actually created it."""
    rows = await conn.execute(
        sqlalchemy.text(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'writing_activity_events'"
        )
    )
    return {name: nullable == "YES" for name, nullable in rows.all()}


async def _seed_novel(conn: AsyncConnection, user_id: _uuid.UUID, novel_id: _uuid.UUID) -> None:
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO novels (id, user_id, title, author, genre, "
            "writing_language, tone, story_structure, logline, synopsis, is_demo) "
            "VALUES (:id, :uid, 'RT Novel', '', '', 'en', '', 'three_act', "
            "'', '', false)"
        ),
        {"id": novel_id, "uid": user_id},
    )


async def _seed_chapter(
    conn: AsyncConnection, novel_id: _uuid.UUID, chapter_id: _uuid.UUID
) -> None:
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO chapters (id, novel_id, title, content, summary, position, "
            "word_count, status, pov_character_id, timeline_position, embeddings_dirty) "
            "VALUES (:id, :nid, 'RT Chapter', '', '', 0, 150, 'draft', '', '', false)"
        ),
        {"id": chapter_id, "nid": novel_id},
    )


async def _insert_event(
    conn: AsyncConnection,
    event_id: _uuid.UUID,
    user_id: _uuid.UUID,
    novel_id: _uuid.UUID | None,
    chapter_id: _uuid.UUID | None,
    delta_words: int,
) -> None:
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO writing_activity_events (id, user_id, novel_id, chapter_id, "
            "delta_words, created_at) "
            "VALUES (:id, :uid, :nid, :cid, :delta, :ts)"
        ),
        {
            "id": event_id,
            "uid": user_id,
            "nid": novel_id,
            "cid": chapter_id,
            "delta": delta_words,
            "ts": _CREATED_AT,
        },
    )


@pytest.mark.schema_mutating
class TestMigration0045RoundTrip:
    """0045 round-trip safety against the shared test DB."""

    async def test_seed_then_downgrade_then_upgrade(self) -> None:
        """Parity + FK contracts hold at head; downgrade drops; up restores empty."""
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        chapter_id = _uuid.uuid4()
        positive_id = _uuid.uuid4()
        negative_id = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                await seed_user(conn, user_id)
                await _seed_novel(conn, user_id, novel_id)
                await _seed_chapter(conn, novel_id, chapter_id)

                # Signed deltas: BOTH signs accepted — ADR-095 deliberately
                # ships no CHECK (chapter deletes are honest negative deltas).
                await _insert_event(conn, positive_id, user_id, novel_id, chapter_id, 120)
                await _insert_event(conn, negative_id, user_id, novel_id, None, -30)

                # RULE-14 parity: the migration-created column set + nullability
                # must match the model metadata exactly — no drift either way.
                model_cols = {c.name: c.nullable for c in WritingActivityEventRow.__table__.columns}
                assert await _db_columns(conn) == model_cols

                assert await _index_exists(conn, "ix_writing_activity_events_user_created")
                assert await _index_exists(conn, "ix_writing_activity_events_novel_id")

                # created_at has NO server default: a raw insert omitting it
                # must be refused (the recorder always supplies the timestamp).
                with pytest.raises(IntegrityError):
                    async with conn.begin_nested():
                        await conn.execute(
                            sqlalchemy.text(
                                "INSERT INTO writing_activity_events (id, user_id, delta_words) "
                                "VALUES (:id, :uid, 5)"
                            ),
                            {"id": _uuid.uuid4(), "uid": user_id},
                        )

                # RESTRICT (ADR-095 D1): deleting a user with writing history
                # must be refused by the DB. SAVEPOINT so ONLY the failing
                # DELETE rolls back (mirrors test_migration_0043).
                with pytest.raises(IntegrityError):
                    async with conn.begin_nested():
                        await conn.execute(
                            sqlalchemy.text("DELETE FROM users WHERE id = :uid"), {"uid": user_id}
                        )

                # SET NULL chapter (ADR-095 D1): chapter deletion is a NORMAL
                # flow — the delta event survives with a nulled reference.
                async with conn.begin_nested():
                    await conn.execute(
                        sqlalchemy.text("DELETE FROM chapters WHERE id = :cid"), {"cid": chapter_id}
                    )
                    row = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT novel_id, chapter_id FROM writing_activity_events "
                                "WHERE id = :id"
                            ),
                            {"id": positive_id},
                        )
                    ).one()
                    assert row[0] == novel_id, "novel link must survive a chapter delete"
                    assert row[1] is None, "chapter deletion must SET NULL the link"

                # SET NULL novel (ADR-095 D1): writing history outlives the
                # novel. The cascade also deletes the chapter — both links null.
                async with conn.begin_nested():
                    await conn.execute(
                        sqlalchemy.text("DELETE FROM novels WHERE id = :nid"), {"nid": novel_id}
                    )
                    row = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT novel_id, chapter_id FROM writing_activity_events "
                                "WHERE id = :id"
                            ),
                            {"id": positive_id},
                        )
                    ).one()
                    assert row[0] is None, "novel deletion must SET NULL the link"
                    assert row[1] is None, "cascaded chapter deletion must SET NULL too"
        finally:
            await eng.dispose()

        # Non-vacuousness guard: the seeds COMMITTED (mirrors test_migration_0043).
        eng = engine()
        try:
            async with eng.connect() as conn:
                seeded = (
                    await conn.execute(
                        sqlalchemy.text("SELECT COUNT(*) FROM writing_activity_events")
                    )
                ).scalar()
                assert seeded == 2, "seeded delta events must persist before the downgrade"
        finally:
            await eng.dispose()

        try:
            run_alembic("downgrade", _PARENT_REVISION)
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert not await _table_exists(conn), "table must be gone after downgrade"
            finally:
                await eng.dispose()

            run_alembic("upgrade", "head")
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert await _table_exists(conn), "table must exist at head"
                    count = (
                        await conn.execute(
                            sqlalchemy.text("SELECT COUNT(*) FROM writing_activity_events")
                        )
                    ).scalar()
                    assert count == 0, "seeded rows do not survive the round trip"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            run_alembic("upgrade", "head")
