"""Throwaway databases for tests that run against a real Postgres.

Each suite gets its own database: the old application's ``narrare_test`` already
has a ``users`` table and its own Alembic history, so it cannot be shared.
"""

import asyncio
from contextlib import suppress

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SERVER = "postgresql+asyncpg://narrare:narrare@localhost:5433"


def url_for(database: str) -> str:
    return f"{SERVER}/{database}"


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
