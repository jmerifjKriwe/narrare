"""One database for pytest's whole session, named before anything binds it.

``app/kernel/db/session.py`` reads its URL once, at import. The first import
decides, and pytest collects ``app/api`` before ``app/capabilities``: without
this file the API tests bind the session to the *development* database, and
every capability conftest then resets a test database that nobody talks to. The
symptom stays quiet — the suite passes while truncating the developer's own data
— until a model change reaches the test database and not the development one.

This file is collected before every test module under ``app/``, so the decision
is made once, in one place. The name is per run — worktree token plus a
per-run token (``test_database``) — so a second pytest run, in a second
worktree or a second process, creates, truncates and drops a database of its
own and cannot reach this one mid-suite (#611). ``pytest_sessionfinish`` then
drops the names this run recorded; databases left behind by a run that died
mid-suite the next run's sweep reclaims. The E2E stacks pass their own URL to
the API process they start; this is only the pytest process's own connection.
"""

import os
from typing import TYPE_CHECKING

import pytest

from app.kernel.db.testsupport import drop_run_databases, ensure_database, test_database, url_for

if TYPE_CHECKING:
    from collections.abc import Iterator

DATABASE = test_database()
ensure_database(DATABASE)
os.environ["NARRE_DATABASE_URL"] = url_for(DATABASE)


@pytest.fixture(scope="session", autouse=True)
def _stop_the_shared_web() -> Iterator[None]:
    """End the one Vite dev server the E2E stacks start, once per process.

    A stack starts the dev server on first use and leaves it running: it is
    stateless, while the API and its database are the state each module owns
    (``app/kernel/testing/stack.py``). This fixture is the other end of that
    lifetime, and it runs in an xdist worker too — where a stack usually lives.
    """
    yield
    from app.kernel.testing.stack import stop_capability_stacks, stop_shared_web

    stop_capability_stacks()
    stop_shared_web()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Drop this run's recorded names once the last test is over."""
    drop_run_databases()
