"""Full stack for the setup E2E: its own database and no local user.

``seed_user=False`` is the point of this suite: the instance must start empty
and be installed through the browser. A first run happens once per database,
so ``fresh_instance`` empties it again before every test — pytest-randomly
shuffles the module, and every test here opens on the setup page.
"""

import asyncio
from collections.abc import Iterator  # noqa: TC003
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.db.testsupport import url_for
from app.kernel.testing.stack import Stack, run_stack

DATABASE = "narrare_v2_setup_e2e"


def _forget_everything() -> None:
    """Back to an uninstalled instance, in a worker thread.

    pytest-asyncio keeps a session loop running, and asyncio.run refuses to
    start a second one in the same thread.
    """

    async def run() -> None:
        """Empty the tables a first run writes; the cascade takes their rows."""
        engine = create_async_engine(url_for(DATABASE))
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("TRUNCATE chunks, documents, novels, chapters, users CASCADE")
                )
        finally:
            await engine.dispose()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, run()).result()


@pytest.fixture(scope="module")
def stack() -> Iterator[Stack]:
    with run_stack(database=DATABASE, seed_user=False) as running:
        yield running


@pytest.fixture(autouse=True)
def fresh_instance(stack: Stack) -> None:
    """Every test starts on a database nobody has set up yet."""
    _forget_everything()
