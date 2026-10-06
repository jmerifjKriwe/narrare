# tests/integration/test_migration_0043_round_trip.py
"""Round-trip test for migration 0043 (STATS-002 — usage_records).

Verifies: at head, a usage record with NULL cost (unpriced) can be inserted
and the FK contracts the spec relies on are enforced by the DB, not just the
ORM — user ON DELETE RESTRICT and novel ON DELETE SET NULL (spec §3.4);
downgrading to 0042 drops the table with its rows (cost telemetry is
non-critical data — documented data loss, spec §6); re-upgrading recreates
it empty.

The repository aggregation semantics on real PG live in
``test_usage_record_aggregation.py`` (RULE-04 split; shared helpers in
``_usage_record_test_support.py``).

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test`` and
CI run it in a dedicated SERIAL phase — never concurrently with other tests.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy.exc import IntegrityError

from tests.integration._usage_record_test_support import (
    JAN_1,
    engine,
    run_alembic,
    seed_user,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# Downgrading to the parent revision applies ONLY 0043's downgrade.
_PARENT_REVISION = "0042_chat_project_optional"


async def _table_exists(conn: AsyncConnection) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'usage_records')"
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


@pytest.mark.schema_mutating
class TestMigration0043RoundTrip:
    """0043 round-trip safety against the shared test DB."""

    async def test_seed_then_downgrade_then_upgrade(self) -> None:
        """Seeded row survives at head; downgrade drops the table; up restores it."""
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        usage_id = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
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
                # NULL cost (unpriced) must be accepted; omitted cache_* columns
                # exercise their server_default 0.
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO usage_records (id, user_id, novel_id, intent, provider, "
                        "model_id, tokens_in, tokens_out, duration_ms, created_at) "
                        "VALUES (:id, :uid, :nid, 'summarize', 'anthropic', 'claude-haiku', "
                        "10, 20, 500, :ts)"
                    ),
                    {"id": usage_id, "uid": user_id, "nid": novel_id, "ts": JAN_1},
                )
                assert await _index_exists(conn, "ix_usage_records_user_created")
                assert await _index_exists(conn, "ix_usage_records_novel_id")

                # RESTRICT (spec §3.4): deleting a user with cost history must
                # be refused by the DB. SAVEPOINT so ONLY the failing DELETE
                # rolls back (mirrors test_migration_0041 — without it the
                # caught error would deactivate the outer transaction).
                with pytest.raises(IntegrityError):
                    async with conn.begin_nested():
                        await conn.execute(
                            sqlalchemy.text("DELETE FROM users WHERE id = :uid"), {"uid": user_id}
                        )

                # SET NULL (spec §3.4): deleting the novel keeps the row,
                # clears the link (asserted inside the savepoint, then undone).
                async with conn.begin_nested():
                    await conn.execute(
                        sqlalchemy.text("DELETE FROM novels WHERE id = :nid"), {"nid": novel_id}
                    )
                    novel_ref = (
                        await conn.execute(
                            sqlalchemy.text("SELECT novel_id FROM usage_records WHERE id = :id"),
                            {"id": usage_id},
                        )
                    ).scalar()
                    assert novel_ref is None, "novel deletion must SET NULL the link"
        finally:
            await eng.dispose()

        # Non-vacuousness guard: the seed COMMITTED (mirrors test_migration_0041).
        eng = engine()
        try:
            async with eng.connect() as conn:
                seeded = (
                    await conn.execute(
                        sqlalchemy.text("SELECT COUNT(*) FROM usage_records WHERE id = :id"),
                        {"id": usage_id},
                    )
                ).scalar()
                assert seeded == 1, "seeded usage record must persist before the downgrade"
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
                        await conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM usage_records"))
                    ).scalar()
                    assert count == 0, "seeded rows do not survive the round trip"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            run_alembic("upgrade", "head")
