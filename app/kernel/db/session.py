"""Async engine and session factory.

The connection is resolved once at import — from ``NARRE_DATABASE_URL``, else the
``NARRE_DB_*`` parts, else the development database (see
:mod:`app.kernel.db.url`) — so a test sets its variables before the app is
imported, which the E2E and integration conftest do.
"""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.kernel.db.url import resolve

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

CONFIG = resolve()
"""Where the connection came from, and its URL; ``main`` logs ``source`` at startup."""

DATABASE_URL = CONFIG.url.render_as_string(hide_password=False)
"""The rendered URL: ``prepare_database`` hands it to alembic through the environment."""

# Bound values include manuscript text; keep them out of SQL exception logs.
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, hide_parameters=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with Session() as session:
        yield session
