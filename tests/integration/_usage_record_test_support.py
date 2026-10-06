"""Shared DB/alembic helpers for the usage-records (STATS-002) integration tests.

RULE-04 support module (house ``_*_support.py`` pattern): both
``test_migration_0043_round_trip.py`` (migration 0043 round-trip safety) and
``test_usage_record_aggregation.py`` (repository aggregation semantics) drive
the same test database and the same alembic setup — this module keeps that
machinery in one place instead of duplicating it. Still test-tree, not
production code (``tests/`` is outside pyright's CI ``include``, see
``pyproject.toml``).
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

if TYPE_CHECKING:
    import uuid as _uuid

    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

# Shared fixed timestamps: the round-trip seed row and the aggregation window
# starts (Jan) both pin 2026-01-01 UTC.
JAN_1 = datetime(2026, 1, 1, tzinfo=UTC)


def db_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test",
    )


def engine() -> AsyncEngine:
    """Fresh NullPool engine per use (mirrors the integration conftest)."""
    return create_async_engine(db_url(), poolclass=NullPool)


def run_alembic(*args: str) -> None:
    """Run an alembic command against the test DB (mirrors integration conftest)."""
    alembic_dir = Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "alembic"
    alembic_ini = alembic_dir.parent / "alembic.ini"
    env = {**os.environ, "DATABASE_URL": db_url(), "PGOPTIONS": "-c lock_timeout=10s"}
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


async def seed_user(conn: AsyncConnection, user_id: _uuid.UUID) -> None:
    """Insert the bare user row usage records must attribute to."""
    await conn.execute(
        sqlalchemy.text(
            "INSERT INTO users (id, email, hashed_password, created_at, "
            "updated_at) VALUES (:id, :email, 'fake_hash', now(), now())"
        ),
        {"id": user_id, "email": f"u-{user_id.hex[:10]}@example.com"},
    )
