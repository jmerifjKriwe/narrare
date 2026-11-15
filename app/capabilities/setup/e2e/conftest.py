"""Full stack for the setup E2E: its own database and no local user.

``seed_user=False`` is the point of this suite: the instance must start empty
and be installed through the browser. A first run happens once per database,
so ``fresh_instance`` empties it again before every test — pytest-randomly
shuffles the module, and every test here opens on an uninstalled instance.

``DATABASE`` is defined here once; the tests import it from this module.
"""

from collections.abc import Iterator  # noqa: TC003

import pytest

from app.kernel.db import testsupport
from app.kernel.testing.db_rows import reset
from app.kernel.testing.stack import Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_setup_e2e")


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("setup", database=DATABASE, seed_user=False)
    yield running


@pytest.fixture(autouse=True)
def fresh_instance(stack: Stack) -> None:
    """Every test starts on a database nobody has set up yet."""
    reset(DATABASE)
