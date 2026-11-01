"""The API suite reads the shared test database; its tables must exist.

Other suites rebuild that schema from the models; this one only needs the
tables to be there — the lifespan tests start the app for real, and the
lifespan itself brings the database to the history's head (it bootstrap-stamps
a models-built schema, design D4, or upgrades a versioned one; the session
fixture runs the same ``init_schema`` first so every test starts from head).
"""

import os
from asyncio import run
from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# A test suite must not write backups; the backup path has its own tests
# (app/kernel/db/tests/test_migrations.py).
os.environ["NARRE_MIGRATION_BACKUP"] = "skip"

from app.api.main import app
from app.kernel.db.testsupport import url_for

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Generator

    from anyio.from_thread import BlockingPortal

DATABASE = "narrare_v2_test"


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Bring the shared test database to the history's head."""
    from app.kernel.db.init import init_schema

    run(init_schema(url_for(DATABASE)))


async def _forget_the_history(database: str) -> None:
    """Drop ``alembic_version`` but keep the tables — the models-built shape."""
    engine = create_async_engine(database)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    finally:
        await engine.dispose()


async def _empty_the_shared_pool() -> None:
    """Dispose the shared engine's pool on the session loop.

    Connections in the pool belong to whichever loop checked them out — the
    session loop's earlier async tests, or a previous client's portal. A
    client's portal starts the lifespan on its own loop, and asyncpg refuses
    a foreign loop's connection outright. Emptying the pool here, while the
    session loop is alive to close what it owns, makes every client start
    fresh; the next session-loop user simply reconnects.
    """
    from app.kernel.db.session import engine

    await engine.dispose()


def _drain_on_the_portal(portal: BlockingPortal | None) -> None:
    """Stop the lane and close the portal loop's connections on their own loop.

    The lane's reset left its connection in the shared pool; disposing from
    another loop after the portal is gone is where the unraisable garbage
    comes from, attributed by pytest to whichever test runs next. Here the
    loop is still alive — and the lifespan's own shutdown then no-ops on an
    already-stopped lane.
    """
    from app.kernel.db.session import engine
    from app.kernel.jobs.runtime import stop_worker

    async def stop_and_drain() -> None:
        await stop_worker(app)
        await engine.dispose()

    assert portal is not None  # a completed __enter__ always left one
    portal.call(stop_and_drain)


@pytest.fixture
async def client() -> AsyncIterator[TestClient]:
    """The started app on a models-created database: tables, no history row.

    The drop runs before startup, so the lifespan's ``prepare_database`` —
    not this suite's session fixture — is what puts the version row back.
    """
    await _forget_the_history(url_for(DATABASE))
    await _empty_the_shared_pool()
    with TestClient(app) as started:
        try:
            yield started
        finally:
            # The cast keeps the argument's type honest; the ignore covers the
            # member access itself — starlette 1.3.1 ships no types for the
            # attribute, so pyright reads it as Unknown. A completed __enter__
            # left a portal; the runtime contract is unchanged.
            _drain_on_the_portal(cast("BlockingPortal | None", started.portal))  # pyright: ignore[reportUnknownMemberType]


@pytest.fixture
async def client_factory() -> AsyncIterator[Callable[[], AbstractContextManager[TestClient]]]:
    """Start the app on demand: a test can drift the database first, then
    catch whatever startup says about it — ``__enter__`` runs the lifespan
    and propagates its error. A startup that refuses never enters the body,
    so there is nothing to drain: ``prepare_database`` left nothing pooled."""

    await _empty_the_shared_pool()

    @contextmanager
    def factory() -> Generator[TestClient]:
        with TestClient(app) as started:
            try:
                yield started
            finally:
                # starlette 1.3.1 ships no types for the attribute — the ignore
                # covers the member access; the cast keeps the argument honest.
                _drain_on_the_portal(cast("BlockingPortal | None", started.portal))  # pyright: ignore[reportUnknownMemberType]

    yield factory
