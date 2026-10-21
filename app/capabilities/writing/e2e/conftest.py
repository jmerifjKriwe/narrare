"""Full stack for the writing E2E: own database, real API, real Next.js dev server.

Ports 8000 and 3100 are deliberate: 3000 belongs to the OpenChamber UI on this
machine, and the old application keeps its own ports while it is still running.
"""

import asyncio
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterator  # noqa: TC003
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from alembic.config import Config
from app.kernel.db.testsupport import ensure_database, url_for
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command

ROOT = Path(__file__).resolve().parents[4]
API_URL = "http://127.0.0.1:8000"
WEB_URL = "http://127.0.0.1:3100"
DATABASE = "narrare_v2_e2e"

# Set before anything imports app.kernel.db.session, whose URL is read at import.
os.environ["NARRE_DATABASE_URL"] = url_for(DATABASE)


def _wait_for(url: str, timeout: float = 180.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:  # noqa: S310  fixed localhost URL
                if response.status < 500:
                    return
        except URLError, TimeoutError:
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not answer within {timeout}s")


async def _clear() -> None:
    engine = create_async_engine(url_for(DATABASE))
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE novels, chapters, users CASCADE"))
    await engine.dispose()


def _prepare() -> None:
    """Schema and clean tables.

    Runs in a worker thread: pytest-asyncio keeps a session loop running, and
    ``asyncio.run`` refuses to start a second one in the same thread.
    """
    ensure_database(DATABASE)
    config = Config(str(ROOT / "app/kernel/db/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "app/kernel/db/migrations"))
    command.upgrade(config, "head")
    asyncio.run(_clear())


@pytest.fixture(scope="session")
def stack() -> Iterator[None]:
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_prepare).result()

    environment = {**os.environ, "NARRE_DATABASE_URL": url_for(DATABASE)}
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app", "--port", "8000"],
        cwd=ROOT,
        env=environment,
        start_new_session=True,
    )
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise RuntimeError("pnpm is not on PATH")
    web = subprocess.Popen(  # noqa: S603  fixed argument list, resolved path
        [pnpm, "dev"],
        cwd=ROOT / "web",
        env=environment,
        start_new_session=True,
    )
    try:
        _wait_for(f"{API_URL}/api/writing/novels")
        _wait_for(WEB_URL)
        yield
    finally:
        # Next runs its server in a child process; kill the whole group or the
        # port stays bound after the test run.
        for process in (web, api):
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=15)
