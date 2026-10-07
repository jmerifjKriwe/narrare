# tests/integration/test_migration_0044_round_trip.py
"""Round-trip test for migration 0044 (STATS-002 budgets — ADR-094).

Verifies against real PG: at head, a ``user_ai_settings`` row inserted
without budget columns gets ``budget_mode='warn'`` (server_default
backfill) and ``monthly_budget_usd`` stays NULL (no budget); the value is
NUMERIC and the CHECK confines ``budget_mode`` to {'warn','block'};
downgrading to 0043 drops both columns (explicit user action — budget
values are re-enterable settings); re-upgrading restores them with the
backfill applied to the surviving row.

DB-level helpers (engine / alembic / seed_user) come from
``_usage_record_test_support.py`` — same machinery as the 0043 round
trip (RULE-04).

NOTE: mutates the shared test DB schema mid-run; the ``finally`` always
restores head. Carries ``@pytest.mark.schema_mutating`` so ``just test``
and CI run it in a dedicated SERIAL phase — never concurrently.
"""

from __future__ import annotations

import uuid as _uuid
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy.exc import IntegrityError

from tests.integration._usage_record_test_support import (
    engine,
    run_alembic,
    seed_user,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

# Downgrading to the parent revision applies ONLY 0044's downgrade.
_PARENT_REVISION = "0043_usage_records"


async def _column_exists(conn: AsyncConnection, column: str) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'user_ai_settings' AND column_name = :col)"
                ),
                {"col": column},
            )
        ).scalar()
    )


async def _budget_mode_check_exists(conn: AsyncConnection) -> bool:
    return bool(
        (
            await conn.execute(
                sqlalchemy.text(
                    "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = :name "
                    "AND conrelid = 'user_ai_settings'::regclass AND contype = 'c')"
                ),
                {"name": "ck_user_ai_settings_budget_mode"},
            )
        ).scalar()
    )


async def _seed_settings(conn: AsyncConnection, user_id: _uuid.UUID) -> None:
    """Insert a settings row omitting the budget columns entirely."""
    await seed_user(conn, user_id)
    await conn.execute(
        sqlalchemy.text("INSERT INTO user_ai_settings (user_id) VALUES (:uid)"),
        {"uid": user_id},
    )


@pytest.mark.schema_mutating
class TestMigration0044RoundTrip:
    """0044 round-trip safety against the shared test DB."""

    async def test_seed_then_downgrade_then_upgrade(self) -> None:
        """Backfill + CHECK hold at head; downgrade drops columns; up restores."""
        run_alembic("upgrade", "head")

        user_id = _uuid.uuid4()
        eng = engine()
        try:
            async with eng.begin() as conn:
                await _seed_settings(conn, user_id)

                # A-5 defaults: omitted columns → NULL budget, 'warn' mode.
                row = (
                    await conn.execute(
                        sqlalchemy.text(
                            "SELECT monthly_budget_usd, budget_mode "
                            "FROM user_ai_settings WHERE user_id = :uid"
                        ),
                        {"uid": user_id},
                    )
                ).one()
                assert row[0] is None, "no budget until the user sets one"
                assert row[1] == "warn", "server_default must backfill 'warn'"
                assert await _budget_mode_check_exists(conn)

                # NUMERIC(10,2) round-trips as Decimal (money, never float).
                await conn.execute(
                    sqlalchemy.text(
                        "UPDATE user_ai_settings SET monthly_budget_usd = 25.5, "
                        "budget_mode = 'block' WHERE user_id = :uid"
                    ),
                    {"uid": user_id},
                )
                row = (
                    await conn.execute(
                        sqlalchemy.text(
                            "SELECT monthly_budget_usd FROM user_ai_settings WHERE user_id = :uid"
                        ),
                        {"uid": user_id},
                    )
                ).one()
                assert row[0] == Decimal("25.50")

                # CHECK: 'bogus' must be refused by the DB. SAVEPOINT so ONLY
                # the failing UPDATE rolls back (mirrors test_migration_0043).
                with pytest.raises(IntegrityError):
                    async with conn.begin_nested():
                        await conn.execute(
                            sqlalchemy.text(
                                "UPDATE user_ai_settings SET budget_mode = 'bogus' "
                                "WHERE user_id = :uid"
                            ),
                            {"uid": user_id},
                        )
        finally:
            await eng.dispose()

        try:
            run_alembic("downgrade", _PARENT_REVISION)
            eng = engine()
            try:
                async with eng.begin() as conn:
                    assert not await _column_exists(conn, "monthly_budget_usd")
                    assert not await _column_exists(conn, "budget_mode")
                    # The settings row itself survives the downgrade.
                    count = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT COUNT(*) FROM user_ai_settings WHERE user_id = :uid"
                            ),
                            {"uid": user_id},
                        )
                    ).scalar()
                    assert count == 1, "settings row must survive the downgrade"
            finally:
                await eng.dispose()

            run_alembic("upgrade", "head")
            eng = engine()
            try:
                async with eng.begin() as conn:
                    row = (
                        await conn.execute(
                            sqlalchemy.text(
                                "SELECT monthly_budget_usd, budget_mode "
                                "FROM user_ai_settings WHERE user_id = :uid"
                            ),
                            {"uid": user_id},
                        )
                    ).one()
                    assert row[0] is None, "re-added column must default to NULL"
                    assert row[1] == "warn", "re-added column must backfill 'warn'"
            finally:
                await eng.dispose()
        finally:
            # Safety net: ALWAYS leave the shared test DB at head.
            run_alembic("upgrade", "head")
