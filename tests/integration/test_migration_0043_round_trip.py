# tests/integration/test_migration_0043_round_trip.py
"""Round-trip test for migration 0043 (STATS-002 — usage_records).

Verifies: at head, a usage record with NULL cost (unpriced) can be inserted
and the FK contracts the spec relies on are enforced by the DB, not just the
ORM — user ON DELETE RESTRICT and novel ON DELETE SET NULL (spec §3.4);
downgrading to 0042 drops the table with its rows (cost telemetry is
non-critical data — documented data loss, spec §6); re-upgrading recreates
it empty.

Also proves the ``UsageRecordRepository`` aggregation semantics against real
PostgreSQL (the unit tests carry a fake session only — same wiring-unit /
semantics-integration split as the notes repository): date_trunc month
bucketing, token/cost sums, COALESCE for an unpriced-only bucket,
``count(*) FILTER`` unpriced_calls, half-open ``[start, end)`` bounds and
per-user attribution isolation.

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test`` and
CI run it in a dedicated SERIAL phase — never concurrently with other tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid as _uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine
from sqlalchemy.pool import NullPool as _NullPool

from narrare.analytics.models import UsageRecordRow
from narrare.analytics.repository import UsageRecordRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# Downgrading to the parent revision applies ONLY 0043's downgrade.
_PARENT_REVISION = "0042_chat_project_optional"

_JAN_1 = datetime(2026, 1, 1, tzinfo=UTC)
_MAR_1 = datetime(2026, 3, 1, tzinfo=UTC)
_APR_1 = datetime(2026, 4, 1, tzinfo=UTC)


def _db_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
    )


def _alembic_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"


def _run_alembic(*args: str) -> None:
    """Run an alembic command against the test DB (mirrors integration conftest)."""
    alembic_dir = _alembic_dir()
    alembic_ini = alembic_dir.parent / "alembic.ini"
    env = {**os.environ, "DATABASE_URL": _db_url(), "PGOPTIONS": "-c lock_timeout=10s"}
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


def _usage(
    user_id: _uuid.UUID,
    *,
    when: datetime,
    intent: str,
    provider: str,
    model: str,
    tin: int,
    tout: int,
    cost: Decimal | None,
) -> UsageRecordRow:
    return UsageRecordRow(
        user_id=user_id,
        intent=intent,
        provider=provider,
        model_id=model,
        tokens_in=tin,
        tokens_out=tout,
        duration_ms=100,
        cost_usd=cost,
        created_at=when,
    )


@pytest.mark.schema_mutating
class TestMigration0043RoundTrip:
    """0043 round-trip safety + repository aggregation semantics on real PG."""

    async def test_aggregate_range_semantics_on_real_pg(self) -> None:
        """Bucketing, sums, COALESCE, FILTER count, [start, end) and isolation."""
        _run_alembic("upgrade", "head")

        user_a = _uuid.uuid4()
        user_b = _uuid.uuid4()
        eng = _create_async_engine(_db_url(), poolclass=_NullPool)
        try:
            async with eng.begin() as conn:
                for uid in (user_a, user_b):
                    await conn.execute(
                        sqlalchemy.text(
                            "INSERT INTO users (id, email, hashed_password, created_at, "
                            "updated_at) VALUES (:id, :email, 'fake_hash', now(), now())"
                        ),
                        {"id": uid, "email": f"u-{uid.hex[:10]}@example.com"},
                    )

            async with AsyncSession(eng) as session:
                # Deterministic month bucketing regardless of the server's TZ GUC.
                await session.execute(sqlalchemy.text("SET TIME ZONE 'UTC'"))
                repo = UsageRecordRepository(session)

                # user_a: priced Jan bucket (2 calls), unpriced Jan bucket
                # (1 row mid-month + 1 row EXACTLY at start — proves >=),
                # priced Feb bucket, and a row EXACTLY at end (proves <).
                await repo.insert(
                    _usage(
                        user_a,
                        when=datetime(2026, 1, 10, 12, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=100,
                        tout=10,
                        cost=Decimal("0.001"),
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=datetime(2026, 1, 20, 12, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=50,
                        tout=20,
                        cost=Decimal("0.002"),
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=datetime(2026, 1, 15, 12, tzinfo=UTC),
                        intent="write",
                        provider="openai",
                        model="gpt-x",
                        tin=70,
                        tout=40,
                        cost=None,
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=_JAN_1,
                        intent="write",
                        provider="openai",
                        model="gpt-x",
                        tin=30,
                        tout=5,
                        cost=None,
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=datetime(2026, 2, 10, 12, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=80,
                        tout=60,
                        cost=Decimal("0.004"),
                    )
                )
                await repo.insert(
                    _usage(
                        user_a,
                        when=_MAR_1,
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=11,
                        tout=12,
                        cost=Decimal("0.009"),
                    )
                )
                # user_b interleaves the SAME month/model as user_a.
                await repo.insert(
                    _usage(
                        user_b,
                        when=datetime(2026, 1, 25, 12, tzinfo=UTC),
                        intent="summarize",
                        provider="anthropic",
                        model="claude-haiku",
                        tin=1000,
                        tout=100,
                        cost=Decimal("0.999"),
                    )
                )

                rows_a = await repo.aggregate_range(user_a, _JAN_1, _MAR_1)
                rows_a_full = await repo.aggregate_range(user_a, _JAN_1, _APR_1)
                rows_b = await repo.aggregate_range(user_b, _JAN_1, _APR_1)

            jan_priced, jan_unpriced, feb = rows_a

            # Month bucketing: date_trunc → first-of-month date (strictly date).
            assert [r.month for r in rows_a] == [date(2026, 1, 1)] * 2 + [date(2026, 2, 1)]
            assert all(type(r.month) is date for r in rows_a)
            # Order: month asc, then cost desc within the month.
            assert [(r.intent, r.model_id) for r in rows_a] == [
                ("summarize", "claude-haiku"),
                ("write", "gpt-x"),
                ("summarize", "claude-haiku"),
            ]
            # Sums + priced bucket.
            assert (jan_priced.calls, jan_priced.tokens_in, jan_priced.tokens_out) == (2, 150, 30)
            assert jan_priced.cost_usd == Decimal("0.003")
            assert jan_priced.unpriced_calls == 0
            # Unpriced-only bucket: COALESCE cost 0, FILTER count 2 (incl. the
            # at-start row → start bound is INCLUSIVE, [ not (.
            assert jan_unpriced.calls == 2
            assert jan_unpriced.tokens_in == 100
            assert jan_unpriced.cost_usd == Decimal("0")
            assert jan_unpriced.unpriced_calls == 2
            # Feb bucket.
            assert feb.calls == 1
            assert feb.cost_usd == Decimal("0.004")
            # Half-open upper bound: the at-end row is NOT in [Jan, Mar) ...
            assert len(rows_a) == 3
            # ... but exists as its own March bucket in [Jan, Apr).
            assert rows_a_full[-1].month == date(2026, 3, 1)
            assert (rows_a_full[-1].calls, rows_a_full[-1].cost_usd) == (1, Decimal("0.009"))
            # Attribution isolation: user_b sees only their own bucket; none of
            # user_a's rows leak into it (and vice versa).
            assert len(rows_b) == 1
            assert (rows_b[0].calls, rows_b[0].tokens_in) == (1, 1000)
            assert rows_b[0].cost_usd == Decimal("0.999")
            assert all(r.cost_usd != Decimal("0.999") for r in rows_a_full)
        finally:
            await eng.dispose()

    async def test_seed_then_downgrade_then_upgrade(self) -> None:
        """Seeded row survives at head; downgrade drops the table; up restores it."""
        _run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        novel_id = _uuid.uuid4()
        usage_id = _uuid.uuid4()
        eng = _create_async_engine(_db_url(), poolclass=_NullPool)
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
                # NULL cost (unpriced) must be accepted; omitted cache_* columns
                # exercise their server_default 0.
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO usage_records (id, user_id, novel_id, intent, provider, "
                        "model_id, tokens_in, tokens_out, duration_ms, created_at) "
                        "VALUES (:id, :uid, :nid, 'summarize', 'anthropic', 'claude-haiku', "
                        "10, 20, 500, :ts)"
                    ),
                    {"id": usage_id, "uid": user_id, "nid": novel_id, "ts": _JAN_1},
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
        eng = _create_async_engine(_db_url(), poolclass=_NullPool)
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
            _run_alembic("downgrade", _PARENT_REVISION)
            eng = _create_async_engine(_db_url(), poolclass=_NullPool)
            try:
                async with eng.begin() as conn:
                    assert not await _table_exists(conn), "table must be gone after downgrade"
            finally:
                await eng.dispose()

            _run_alembic("upgrade", "head")
            eng = _create_async_engine(_db_url(), poolclass=_NullPool)
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
            _run_alembic("upgrade", "head")
