"""A real stack for capability E2E tests: own database, real API, real Next.js.

Nothing here is a fake. The browser, the HTTP API and Postgres are the ones the
product runs; only the LLM provider will ever be replaced, and only at its own
boundary.

Each capability's ``e2e/conftest.py`` wraps :func:`run_stack` in a module-scoped
fixture. Module scope matters: a session-scoped stack would outlive the module
and keep ports 8000 and 3100 bound while the next capability starts its own.
"""

import asyncio
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Generator  # noqa: TC003
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from os import environ
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.kernel.auth import LOCAL_USER_ID
from app.kernel.db.init import reset_schema
from app.kernel.db.testsupport import ensure_database, url_for

ROOT = Path(__file__).resolve().parents[3]

# Ports and shutdown grace are configuration: a second stack, or a busy port on
# this machine, must not need a code edit. The defaults are the ones the docs use.
API_PORT = int(environ.get("NARRE_E2E_API_PORT", "8000"))
WEB_PORT = int(environ.get("NARRE_E2E_WEB_PORT", "3100"))
SHUTDOWN_TIMEOUT = float(environ.get("NARRE_E2E_SHUTDOWN_TIMEOUT", "15"))


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


async def _reset(database: str, seed_user: bool) -> None:
    engine = create_async_engine(url_for(database))
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE chunks, documents, novels, chapters, users CASCADE")
        )
        if seed_user:
            # An installed instance: setup only asks whether the local user exists.
            await connection.execute(
                text("INSERT INTO users (id, created_at) VALUES (:id, now())"),
                {"id": LOCAL_USER_ID},
            )
    await engine.dispose()


def _prepare(database: str, seed_user: bool) -> None:
    """Schema from the models, then clean tables.

    Runs in a worker thread: pytest-asyncio keeps a session loop running, and
    ``asyncio.run`` refuses to start a second one in the same thread.
    """
    ensure_database(database)
    # Explicit URL per stack: the process environment is set once, but several
    # capability stacks run one after another in the same pytest process.
    # Reset, not just create: an E2E database is throwaway, and rebuilding it
    # from the models is what proves the schema the tests run against.
    asyncio.run(reset_schema(url_for(database)))
    asyncio.run(_reset(database, seed_user))


@contextmanager
def run_stack(*, database: str, seed_user: bool) -> Generator[None]:
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_prepare, database, seed_user).result()

    environment = {**os.environ, "NARRE_DATABASE_URL": url_for(database)}
    api = subprocess.Popen(  # noqa: S603  fixed argument list, this interpreter
        [sys.executable, "-m", "uvicorn", "app.api.main:app", "--port", str(API_PORT)],
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
        _wait_for(f"http://127.0.0.1:{API_PORT}/openapi.json")
        _wait_for(f"http://127.0.0.1:{WEB_PORT}")
        yield
    finally:
        # Next runs its server in a child process; kill the whole group or the
        # port stays bound after the test run.
        for process in (web, api):
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=SHUTDOWN_TIMEOUT)
