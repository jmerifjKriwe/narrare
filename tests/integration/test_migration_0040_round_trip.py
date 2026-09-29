"""Round-trip safety test for migration 0040 (C2 — drift persistence).

Verifies the 0040 upgrade/downgrade is round-trip safe: with a seeded
``series_drift_results`` row present, downgrading to the parent revision
(0039) drops the table with its rows, and re-upgrading rebuilds the schema.
Uses subprocess alembic + its own connections (NOT the rolled-back
``db_session``, which assumes head) and always restores head in a
``finally``.

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test`` and
CI run it in a dedicated SERIAL phase — it must never run concurrently with
other tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid as _uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.pool import NullPool as _NullPool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# The parent revision: downgrading to it applies ONLY 0040's downgrade (the
# focused round-trip under test), rather than ``base``.
_PARENT_REVISION = "0039_series_voice"


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
            sys.executable,
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
                    "WHERE table_name = 'series_drift_results')"
                )
            )
        ).scalar()
    )


@pytest.mark.schema_mutating
class TestMigration0040RoundTrip:
    """The 0040 upgrade/downgrade is round-trip safe with a seeded row."""

    async def test_seed_drift_row_then_downgrade_then_upgrade(self) -> None:
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
        )

        # 1. Ensure we start at head (0040 applied).
        _run_alembic("upgrade", "head")

        # 2. Seed user + novel + one drift row (the data shape 0040 owns).
        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
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
                        "INSERT INTO series_drift_results (novel_id, result, input_fingerprint) "
                        'VALUES (:nid, \'{"consistency": {"summary": "rt"}}\'::jsonb, :fp)'
                    ),
                    {"nid": novel_id, "fp": "a" * 64},
                )
                assert (
                    await conn.execute(sqlalchemy.text("SELECT COUNT(*) FROM series_drift_results"))
                ).scalar() == 1
        finally:
            await eng.dispose()

        try:
            # 3. Downgrade to the parent revision — drops the table with its rows.
            _run_alembic("downgrade", _PARENT_REVISION)

            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert not await _table_exists(conn), "table must be gone after downgrade"
            finally:
                await eng.dispose()

            # 4. Upgrade back to head — rebuilds the table (rows do not return:
            #    derived analysis artifacts, safe to lose).
            _run_alembic("upgrade", "head")

            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert await _table_exists(conn), "table must exist at head"
                    count = (
                        await conn.execute(
                            sqlalchemy.text("SELECT COUNT(*) FROM series_drift_results")
                        )
                    ).scalar()
                    assert count == 0, "seeded rows do not survive the round trip"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            _run_alembic("upgrade", "head")
