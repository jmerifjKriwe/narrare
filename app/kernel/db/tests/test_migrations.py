"""The migration gates (design D3.1 and D3.2 of the schema-migrations design).

Two of the four design gates live here for now: the history has exactly one
head, and an empty database replayed to head is indistinguishable from what
the models declare. The second is the gate that keeps the two schema paths
identical (D12): tests build from the models, `just db-init` replays the
history, and this test is the only thing that proves both say the same thing.
"""

import asyncio
from os import environ
from typing import TYPE_CHECKING, Any

import pytest
from alembic import command
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.migrate import default_config, diff_against_models, head_revision

if TYPE_CHECKING:
    from collections.abc import Iterator

    from alembic.config import Config
    from sqlalchemy.engine import Connection


@pytest.fixture(autouse=True)
def _restore_database_url() -> Iterator[None]:
    """Put ``NARRE_DATABASE_URL`` back after a test exported its own URL."""
    previous = environ.get("NARRE_DATABASE_URL")
    yield
    if previous is None:
        environ.pop("NARRE_DATABASE_URL", None)
    else:
        environ["NARRE_DATABASE_URL"] = previous


def alembic_config(url: str) -> Config:
    """The repo's alembic.ini, aimed at the gate's database.

    env.py reads the URL from ``NARRE_DATABASE_URL`` — the only URL source —
    so aiming a run at a database means exporting it, the way
    ``app/conftest.py`` does for the whole suite. The autouse fixture above
    restores the previous value when the test ends.
    """
    environ["NARRE_DATABASE_URL"] = url
    return default_config()


def _diff_from_models(connection: Connection, url: str) -> list[Any]:
    """The comparison, on the sync facade ``run_sync`` hands over."""
    return diff_against_models(alembic_config(url), connection)


def test_migrations_have_one_head() -> None:
    assert head_revision().count(",") == 0 and head_revision()


async def test_empty_database_migrated_equals_the_models(url: str) -> None:
    # env.py drives alembic through an asyncio.run of its own, which cannot
    # start inside this test's loop; the upgrade gets its own thread.
    await asyncio.to_thread(command.upgrade, alembic_config(url), "head")

    diff: list[Any] = []
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            diff = await connection.run_sync(
                lambda sync_connection: _diff_from_models(sync_connection, url)
            )
    finally:
        await engine.dispose()
    assert diff == []
