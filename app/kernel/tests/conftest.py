"""Kernel suite fixtures for tests that need the shared test database.

Not every kernel test touches the database (configuration, providers), so
nothing here is autouse: a module opts in with ``usefixtures``. The pattern is
the capability suites' — ``app/conftest.py`` names the database and the app
binds it; this file says what to rebuild and what a test starts from.
"""

from asyncio import run

import pytest
from sqlalchemy import text

from app.kernel.db.testsupport import url_for

DATABASE = "narrare_v2_test"


@pytest.fixture(scope="session")
def schema() -> None:
    """Rebuild the schema from the models: what the tests see is the source."""
    from app.kernel.db.init import reset_schema

    run(reset_schema(url_for(DATABASE)))


@pytest.fixture
async def empty_tables(schema: None) -> None:
    """Start a database test from empty tables, in a schema that exists.

    The ``schema`` argument is the point: pytest-randomly orders modules and
    functions, and a fresh CI database has no tables at all, so any database
    test can be the first one of a run. Without the dependency it truncates
    tables nobody has built yet. The capability suites make their schema
    autouse; this suite keeps it opt-in so a run that never touches the
    database never rebuilds it.
    """
    # Imported here: the module reads its URL once, at import.
    from app.kernel.db.session import Session

    async with Session() as session:
        await session.execute(text("TRUNCATE jobs, users CASCADE"))
        await session.commit()
