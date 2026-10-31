"""The API suite reads the shared test database; its tables must exist.

Other suites rebuild that schema from the models; this one needs the same,
because the lifespan test starts the jobs worker, whose startup reset writes
to the jobs table. ``reset_schema`` is therefore the fixture's call, exactly
as every other suite's — design D12's rule: tests create the schema from the
models, and the migration gate in ``app/kernel/db/tests/test_migrations.py``
proves the replayed history equals it.
"""

from asyncio import run

import pytest

from app.kernel.db.testsupport import url_for

DATABASE = "narrare_v2_test"


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Rebuild the shared test database's schema from the models."""
    from app.kernel.db.init import reset_schema

    run(reset_schema(url_for(DATABASE)))
