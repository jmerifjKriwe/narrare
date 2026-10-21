"""Full stack for the chat E2E: own database, real API, real Next.js.

Module scope: the stack must be gone before the next capability's stack binds the
same ports.
"""

from collections.abc import Iterator  # noqa: TC003

import pytest
from app.kernel.testing.stack import run_stack


@pytest.fixture(scope="module")
def stack() -> Iterator[None]:
    with run_stack(database="narrare_v2_chat_e2e", seed_user=True):
        yield
