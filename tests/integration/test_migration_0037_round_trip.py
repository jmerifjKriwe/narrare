"""Round-trip safety test for migration 0037 (T12).

Split from ``test_migration_0037.py`` to respect the RULE-04 400-line test-file
limit. Verifies the 0037 upgrade/downgrade is round-trip safe even when
Series-Canon KB rows (``novel_id IS NULL``) are present — the data shape that
would block a naive downgrade (restoring ``novel_id NOT NULL``).

The downgrade deletes Canon rows before restoring ``NOT NULL`` (T5), so seeding
Canon data then downgrading to the parent revision and re-upgrading succeeds and
leaves the schema intact. Uses subprocess alembic + its own connections (NOT the
rolled-back ``db_session``, which assumes head) and always restores head in a
``finally``.

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always restores
head. Carries ``@pytest.mark.schema_mutating`` so ``just test`` and CI run it in
a dedicated SERIAL phase (a second pytest invocation without xdist) — it must
never run concurrently with other tests.
"""

from __future__ import annotations

import os
import subprocess
import uuid as _uuid
from pathlib import Path

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.pool import NullPool as _NullPool

# The parent revision: downgrading to it applies ONLY 0037's downgrade (the
# focused round-trip under test), rather than ``base`` which would tear down the
# entire migration history. 0037's symmetry is what the ADR's "round-trip safe"
# claim covers.
_PARENT_REVISION = "0036_author_voice_column"


def _alembic_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"


def _run_alembic(*args: str) -> None:
    """Run an alembic command against the test DB (mirrors integration conftest).

    ``PGOPTIONS`` sets a short ``lock_timeout`` so a DDL lock conflict fails fast
    instead of hanging the suite.
    """
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


def _decode(value: object) -> str:
    """Decode asyncpg's pg_catalog ``"char"`` (returned as bytes) for comparison."""
    if isinstance(value, (bytes, bytearray)):
        return value.decode()
    return str(value)


@pytest.mark.schema_mutating
class TestMigration0037RoundTrip:
    """The 0037 upgrade/downgrade is round-trip safe even with Canon data (T12).

    Runs in the serial ``schema_mutating`` phase (``just test`` / CI), never
    under xdist: it downgrades and re-upgrades the SHARED test-DB schema, so
    any concurrently running test could hit ``column does not exist``.
    """

    async def test_seed_canon_then_downgrade_then_upgrade(self) -> None:
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
        )

        # 1. Ensure we start at head (0037 applied).
        _run_alembic("upgrade", "head")

        # 2. Seed a Series-Canon KB row (novel_id IS NULL) — the data shape that
        #    would block a naive downgrade (restoring novel_id NOT NULL).
        series_id = _uuid.uuid4()
        canon_id = _uuid.uuid4()
        eng = _create_async_engine(db_url, poolclass=_NullPool)
        try:
            async with eng.begin() as conn:
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO series (id, user_id, title) VALUES (:id, :uid, 'RT Series')"
                    ),
                    {"id": series_id, "uid": _uuid.uuid4()},
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO kb_entries (id, novel_id, series_id, entity_type, "
                        "name, slug) VALUES (:id, NULL, :sid, 'system', 'Canon Lore', 'canon-lore')"
                    ),
                    {"id": canon_id, "sid": series_id},
                )
                canon_count = (
                    await conn.execute(
                        sqlalchemy.text("SELECT COUNT(*) FROM kb_entries WHERE novel_id IS NULL")
                    )
                ).scalar()
                assert canon_count == 1
        finally:
            await eng.dispose()

        try:
            # 3. Downgrade to the parent revision — must succeed by deleting the
            #    Canon rows before restoring novel_id NOT NULL (T12 / T5).
            _run_alembic("downgrade", _PARENT_REVISION)

            # 4. After downgrade: Canon rows are gone, novel_id is NOT NULL again,
            #    and the old (novel_id, slug) unique constraint is restored.
            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    canon_count = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT COUNT(*) FROM kb_entries WHERE novel_id IS NULL"
                            )
                        )
                    ).scalar()
                    assert canon_count == 0, "Canon rows must be deleted on downgrade"
                    novel_id_nullable = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT is_nullable FROM information_schema.columns "
                                "WHERE table_name = 'kb_entries' AND column_name = 'novel_id'"
                            )
                        )
                    ).scalar()
                    assert novel_id_nullable == "NO", "novel_id must be NOT NULL after downgrade"
                    old_uq = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT EXISTS (SELECT 1 FROM pg_constraint "
                                "WHERE conname = 'uq_kb_entries_novel_slug')"
                            )
                        )
                    ).scalar()
                    assert old_uq, "old (novel_id, slug) unique constraint must be restored"
            finally:
                await eng.dispose()

            # 5. Upgrade back to head — rebuilds 0037 (columns, partial indexes, CHECK).
            _run_alembic("upgrade", "head")

            # 6. At head again: the scope-invariant CHECK is back and novel_id is
            #    nullable again (Canon rows can exist once more).
            eng = _create_async_engine(db_url, poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    ck = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT contype FROM pg_constraint "
                                "WHERE conname = 'ck_kb_entries_scope_invariant'"
                            )
                        )
                    ).scalar()
                    assert _decode(ck) == "c", "scope-invariant CHECK must exist at head"
                    novel_id_nullable = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT is_nullable FROM information_schema.columns "
                                "WHERE table_name = 'kb_entries' AND column_name = 'novel_id'"
                            )
                        )
                    ).scalar()
                    assert novel_id_nullable == "YES", "novel_id must be nullable at head"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head, even if an
            # assertion failed, so the rest of the integration suite is unaffected.
            _run_alembic("upgrade", "head")
