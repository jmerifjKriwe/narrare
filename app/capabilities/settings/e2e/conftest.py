"""Full stack for the settings E2E: own database, an installed instance.

The user is seeded (setup is done); the language choice itself must be made
through the browser, because that is what the test proves.
"""

from collections.abc import Iterator  # noqa: TC003

import pytest

from app.kernel.db import testsupport
from app.kernel.testing.stack import Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_settings_e2e")


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("settings", database=DATABASE, seed_user=True)
    yield running
