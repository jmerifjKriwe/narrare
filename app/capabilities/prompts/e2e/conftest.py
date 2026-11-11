"""Full stack for the prompts E2E: own database, real API, real web app.

Module scope: the API and its database must be gone before the next capability's
stack binds the same API port. The web server is the exception — one Vite process
serves every stack in a pytest process (see ``app/kernel/testing/stack.py``).
"""

from collections.abc import Iterator  # noqa: TC003

import pytest

from app.kernel.db import testsupport
from app.kernel.testing.stack import Stack, run_stack

DATABASE = testsupport.test_database("narrare_v2_prompts_e2e")


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    with run_stack(database=DATABASE, seed_user=True) as running:
        yield running
