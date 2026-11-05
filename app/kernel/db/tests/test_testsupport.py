"""The test server's address is a choice the environment makes.

Two checkouts share one machine: the compose default (``localhost:5433``)
belongs to whichever stack bound it first, and a second run — a worktree, a
PR gate — must be able to aim its suites at its own server without editing
code. ``NARRE_TEST_DATABASE_URL`` is that aim; every suite and every E2E
stack reaches its database through ``url_for``, so the one constant is the
one door.
"""

from importlib import reload
from os import environ

from app.kernel.db import testsupport

OVERRIDE = "postgresql+asyncpg://narrare:narrare@localhost:5434"
DEFAULT = "postgresql+asyncpg://narrare:narrare@localhost:5433"


def _restore(carried: str | None) -> None:
    """Put the environment back and rebind the module to it.

    A reload rebinds the module global for every later importer in this
    process; without this, one test's address would leak into every suite
    that runs after it.
    """
    if carried is None:
        environ.pop("NARRE_TEST_DATABASE_URL", None)
    else:
        environ["NARRE_TEST_DATABASE_URL"] = carried
    reload(testsupport)


def test_the_server_honours_the_environment_override() -> None:
    carried = environ.get("NARRE_TEST_DATABASE_URL")
    environ["NARRE_TEST_DATABASE_URL"] = OVERRIDE
    try:
        module = reload(testsupport)
        assert module.SERVER == OVERRIDE
        # The suites reach their database through the same door.
        assert module.url_for("narrare_v2_test").startswith(OVERRIDE)
    finally:
        _restore(carried)


def test_the_server_defaults_to_the_compose_address() -> None:
    carried = environ.get("NARRE_TEST_DATABASE_URL")
    environ.pop("NARRE_TEST_DATABASE_URL", None)
    try:
        assert reload(testsupport).SERVER == DEFAULT
    finally:
        _restore(carried)
