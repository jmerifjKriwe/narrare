"""Own database for the v2 tree, created on demand.

The shared ``narrare_test`` database belongs to the old application and already has
a ``users`` table and its own Alembic history; the two schemas cannot share a name.
"""

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE = "narrare_v2_test"


async def _ensure_database() -> None:
    engine = create_async_engine(
        "postgresql+asyncpg://narrare:narrare@localhost:5433/postgres",
        isolation_level="AUTOCOMMIT",
    )
    async with engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DATABASE},
        )
        if not exists:
            await connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    await engine.dispose()


asyncio.run(_ensure_database())

os.environ["NARRE_DATABASE_URL"] = (
    f"postgresql+asyncpg://narrare:narrare@localhost:5433/{TEST_DATABASE}"
)
