"""Throwaway databases for tests that run against a real Postgres.

Each suite gets its own database: they are created and dropped per run, and a
shared database would carry one suite's rows into the next.
"""

import asyncio
from contextlib import suppress
from uuid import UUID  # noqa: TC003

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

SERVER = "postgresql+asyncpg://narrare:narrare@localhost:5433"


def url_for(database: str) -> str:
    return f"{SERVER}/{database}"


async def drop_every_table(database_url: str) -> None:
    """Drop every table and view in the public schema — a throwaway database again.

    The one drop-everything, shared by ``reset_schema``, the migration
    gates' conftest and the gates themselves. Thoroughness matters: leftover
    tables from an older schema version would turn "empty database" tests
    into "previously migrated" ones, and ``metadata.drop_all`` alone leaves
    those behind and then fails on the next run. Dropping tables (not the
    whole schema) keeps the vector extension's types registered, so pooled
    connections do not hit stale type OIDs. Views can depend on tables;
    they are dropped too.
    """
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        result = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        for (table_name,) in result.fetchall():
            await connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        result = await connection.execute(
            text("SELECT viewname FROM pg_views WHERE schemaname = 'public'")
        )
        for (view_name,) in result.fetchall():
            await connection.execute(text(f'DROP VIEW IF EXISTS "{view_name}" CASCADE'))
    await engine.dispose()


async def seed_user(user_id: UUID) -> None:
    """The users row a user-owned test row needs: the key reaches users."""
    from app.kernel.contracts.models import User
    from app.kernel.db.session import Session

    async with Session() as session:
        await session.execute(insert(User).values(id=user_id).on_conflict_do_nothing())
        await session.commit()


async def _ensure(database: str) -> None:
    engine = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    async with engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database}
        )
        if not exists:
            # A parallel pytest worker may create it between the check and here.
            with suppress(Exception):
                await connection.execute(text(f'CREATE DATABASE "{database}"'))
    await engine.dispose()


def ensure_database(database: str) -> None:
    asyncio.run(_ensure(database))
