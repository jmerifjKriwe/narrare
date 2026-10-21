"""Async engine and session factory.

The URL is read once at import, so a test sets ``NARRE_DATABASE_URL`` before the
app is imported (the E2E and integration conftest do exactly that).
"""

from os import environ
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

DATABASE_URL = environ.get(
    "NARRE_DATABASE_URL",
    "postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_v2_dev",
)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with Session() as session:
        yield session
