"""The API suite reads the shared test database; its tables must exist.

Other suites rebuild that schema from the models; this one only needs the
tables to be there — the lifespan test starts the jobs worker, whose startup
reset writes to the jobs table. ``init_schema`` is the idempotent form: it
creates what is missing and leaves the rest alone.
"""

from asyncio import run

import pytest

from app.kernel.db.testsupport import url_for

DATABASE = "narrare_v2_test"


@pytest.fixture(scope="session", autouse=True)
def schema() -> None:
    """Create missing tables; existing ones stay untouched."""
    from app.kernel.db.init import init_schema

    run(init_schema(url_for(DATABASE)))
