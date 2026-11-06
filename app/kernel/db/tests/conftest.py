"""The migration gates' own database: one per run named for ``narrare_v2_migrations``.

``app/conftest.py`` binds the pytest process to its per-run test database for
every other suite; the migration gates need a database nothing else touches
under any prefix, so the gates name one per run of their own prefix and
``NARRE_DATABASE_URL`` is re-aimed by the tests' own helpers.
"""

from asyncio import run
from typing import TYPE_CHECKING

import pytest

from app.kernel.db.migrate import ensure_extensions
from app.kernel.db.testsupport import drop_every_table, ensure_database, test_database, url_for

if TYPE_CHECKING:
    from collections.abc import Iterator

DATABASE = test_database("narrare_v2_migrations")


@pytest.fixture(scope="module")
def url() -> Iterator[str]:
    """The URL the migration gates aim alembic at.

    Extensions are per-database and ``ensure_database`` only issues
    ``CREATE DATABASE``: on a fresh database the baseline's ``vector`` column
    has no type until the same pre-step production runs (``ensure_extensions``)
    has created them — otherwise the first test dies with
    ``type "vector" does not exist``.
    """
    ensure_database(DATABASE)
    run(drop_every_table(url_for(DATABASE)))
    run(ensure_extensions(url_for(DATABASE)))
    yield url_for(DATABASE)
