"""Full stack for the planning E2E: own database, real API, real web app.

Hebel 2: stack acquired once per worker and reused across planning modules.
"""

from collections.abc import Iterator  # noqa: TC003

import pytest

from app.kernel.db import testsupport
from app.kernel.testing.stack import Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_planning_e2e")


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("planning", database=DATABASE, seed_user=True)
    yield running
