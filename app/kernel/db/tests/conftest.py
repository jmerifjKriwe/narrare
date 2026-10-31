"""The migration gates' own database: ``narrare_v2_migrations``, always empty.

``app/conftest.py`` binds the pytest process to ``narrare_v2_test`` for every
other suite; the migration gates need a database nothing else touches, so
``NARRE_DATABASE_URL`` is re-aimed per run by the tests' own helpers.
"""

from asyncio import run
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import ensure_database, url_for

if TYPE_CHECKING:
    from collections.abc import Iterator

DATABASE = "narrare_v2_migrations"


async def _drop_every_table() -> None:
    """Drop whatever an earlier pytest run left in the gates' database.

    ``ensure_database`` only creates a missing database. The gate's claim is
    "an *empty* database migrated equals the models", so leftover tables from
    a previous run would quietly weaken it into "a previously migrated one
    still equals the models" — the drop keeps the replay honest every run.
    """
    engine = create_async_engine(url_for(DATABASE))
    async with engine.begin() as connection:
        result = await connection.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        for (table_name,) in result.fetchall():
            await connection.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
    await engine.dispose()


@pytest.fixture(scope="module")
def url() -> Iterator[str]:
    """The URL the migration gates aim alembic at."""
    ensure_database(DATABASE)
    run(_drop_every_table())
    yield url_for(DATABASE)
