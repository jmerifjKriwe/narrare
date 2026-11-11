"""Full stack for the writing E2E: own database, real API, real web app.

Hebel 2 pilot: the stack is acquired once per worker process and reused by
every writing test module (see ``app/kernel/testing/stack.py::acquire_stack``);
it is not stopped between modules. Teardown happens at session end.
"""

from collections.abc import Iterator  # noqa: TC003

import pytest

from app.kernel.db import testsupport
from app.kernel.testing.stack import Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_e2e")


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("writing", database=DATABASE, seed_user=True)
    yield running
    # Intentionally no teardown: the stack persists for the next writing module.
