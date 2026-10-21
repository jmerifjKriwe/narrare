"""Full stack for the setup E2E: its own database and no local user.

``seed_user=False`` is the point of this suite: the instance must start empty and
be installed through the browser.
"""

from collections.abc import Iterator  # noqa: TC003

import pytest

from app.kernel.testing.stack import run_stack


@pytest.fixture(scope="module")
def stack() -> Iterator[None]:
    with run_stack(database="narrare_v2_setup_e2e", seed_user=False):
        yield
