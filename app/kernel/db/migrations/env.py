"""Alembic environment. Async engine, tables from the kernel models."""

from asyncio import run
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.contracts import models  # noqa: F401  registers the tables
from app.kernel.db.base import Base
from app.kernel.db.session import DATABASE_URL

if TYPE_CHECKING:
    from sqlalchemy import Connection

target_metadata = Base.metadata

# The caller may target another database than the app default (the E2E harness
# does, one stack per capability).
URL = context.config.get_main_option("sqlalchemy.url") or DATABASE_URL


def _migrate(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run() -> None:
    engine = create_async_engine(URL)
    async with engine.connect() as connection:
        await connection.run_sync(_migrate)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run(_run())
