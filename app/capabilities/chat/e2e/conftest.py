"""Full stack for the chat E2E: own database, real API, real web app.

Module scope: the API and its database must be gone before the next capability's
stack binds the same API port. The web server is the exception — one Vite process
serves every stack in a pytest process (see ``app/kernel/testing/stack.py``).
"""

from collections.abc import Iterator  # noqa: TC003

import pytest

from app.kernel.db import testsupport
from app.kernel.testing.stack import Stack, acquire_stack

DATABASE = testsupport.test_database("narrare_v2_chat_e2e")


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    running = acquire_stack("chat", database=DATABASE, seed_user=True)
    yield running
