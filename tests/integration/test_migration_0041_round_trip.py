"""Round-trip safety test for migration 0041 (NOTES-001 — scratchpad).

Verifies the 0041 upgrade/downgrade is round-trip safe AND that the schema
contracts the service layer relies on actually exist at head: the scope
invariant CHECK and the note-type CHECK (RULE-14 verification, mirroring
test_migration_0040_round_trip.py).

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test`` and
CI run it in a dedicated SERIAL phase — never concurrently with other tests.
"""

from __future__ import annotations

import os
import subprocess
import uuid as _uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.pool import NullPool as _NullPool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# Downgrading to the parent revision applies ONLY 0041's downgrade.
_PARENT_REVISION = "0040_series_drift_results"


def _alembic_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"


def _run_alembic(*args: str) -> None:
    """Run an alembic command against the test DB (mirrors integration conftest)."""
    alembic_dir = _alembic_dir()
    alembic_ini = alembic_dir.parent / "alembic.ini"
    db_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
    )
    env = {**os.environ, "DATABASE_URL": db_url, "PGOPTIONS": "-c lock_timeout=10s"}
    subprocess.run(
        [
            "python",
            "-m",
            "alembic",
            "-c",
            str(alembic_ini) if alembic_ini.exists() else "alembic.ini",
            *args,
        ],
        env=env,
        cwd=alembic_dir.parent,
        check=True,
        capture_output=True,
    )


async def _table_exists(conn: AsyncConnection) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'notes')"
                )
            )
        ).scalar()
    )


async def _constraint_exists(conn: AsyncConnection, name: str) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = :name)"
                ),
                {"name": name},
            )
        ).scalar()
    )


@pytest.mark.schema_mutating
class TestMigration0041RoundTrip:
    """The 0041 upgrade/downgrade is round-trip safe with a seeded row."""

    async def test_seed_note_then_downgrade_then_upgrade(self) -> None:
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
        )

        # 1. Ensure we start at head (0041 applied).
        _run_alembic("upgrade", "head")

        # 2. Seed user + novel + series + one note (the data shape 0041 owns).
        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        series_id = _uuid.uuid4()
        note_id = _uuid.uuid4()
        eng = _create_async_engine(db_url, poolclass=_NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
                        "VALUES (:id, :email, 'fake_hash', now(), now())"
                    ),
                    {"id": user_id, "email": f"u-{user_id.hex[:10]}@example.com"},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO novels (id, user_id, title, author, genre, "
                        "writing_language, tone, story_structure, logline, synopsis, is_demo) "
                        "VALUES (:id, :uid, 'RT Novel', '', '', 'en', '', 'three_act', "
                        "'', '', false)"
                    ),
                    {"id": novel_id, "uid": user_id},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO series (id, user_id, title, status) "
                        "VALUES (:id, :uid, 'RT Series', 'draft')"
                    ),
                    {"id": series_id, "uid": user_id},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO notes (id, user_id, title, content, note_type, "
                        "tags, novel_id) "
                        "VALUES (:id, :uid, 'RT Note', 'body', 'idea', '{\"plot\"}', :nid)"
                    ),
                    {"id": note_id, "uid": user_id, "nid": novel_id},
                )
                assert await _constraint_exists(conn, "ck_notes_scope_invariant")
                assert await _constraint_exists(conn, "ck_notes_note_type")

                # 3. The scope invariant is enforced by the DB, not just the
                #    ORM: both links set → IntegrityError. The probe runs
                #    inside a SAVEPOINT (begin_nested) so ONLY the failing
                #    INSERT rolls back. Without it, the caught error would
                #    deactivate the outer transaction and the block-exit
                #    commit would silently persist nothing — leaving the
                #    post-round-trip count==0 assertion below vacuous
                #    (verified empirically: seeds do not survive a caught
                #    IntegrityError without the savepoint).
                with pytest.raises(IntegrityError):
                    async with conn.begin_nested():
                        await conn.execute(
                            sqlalchemy.text(
                                "INSERT INTO notes (id, user_id, content, note_type, tags, "
                                "novel_id, series_id) "
                                "VALUES (:id, :uid, 'both', 'idea', '{}', :nid, :sid)"
                            ),
                            {
                                "id": _uuid.uuid4(),
                                "uid": user_id,
                                "nid": novel_id,
                                "sid": series_id,
                            },
                        )
        finally:
            await eng.dispose()

        # 3.5 Non-vacuousness guard: the seed COMMITTED (the savepoint kept
        # the outer transaction viable), so the row provably exists before
        # the downgrade — otherwise the count==0 assertion after the
        # upgrade would pass even if the round trip wrongly kept rows.
        eng = _create_async_engine(db_url, poolclass=_NullPool)
        try:
            async with eng.connect() as conn:
                seeded = (
                    await conn.execute(
                        sqlalchemy.text("SELECT COUNT(*) FROM notes WHERE id = :nid"),
                        {"nid": note_id},
                    )
                ).scalar()
                assert seeded == 1, "seeded note must persist before the downgrade"
        finally:
            await eng.dispose()

        try:
            # 4. Downgrade to the parent revision — drops the table with its rows.
            _run_alembic("downgrade", _PARENT_REVISION)
            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert not await _table_exists(conn), "table must be gone after downgrade"
            finally:
                await eng.dispose()

            # 5. Upgrade back to head — table + constraints rebuilt. The
            # count==0 assertion is meaningful because step 3.5 proved the
            # seed existed before the downgrade: upgrade must NOT resurrect
            # dropped rows.
            _run_alembic("upgrade", "head")
            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert await _table_exists(conn), "table must exist at head"
                    assert await _constraint_exists(conn, "ck_notes_scope_invariant")
                    count = (
                        await conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM notes"))
                    ).scalar()
                    assert count == 0, "seeded rows do not survive the round trip"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            _run_alembic("upgrade", "head")
