"""A real stack for capability E2E tests: own database, real API, real web app.

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
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Generator  # noqa: TC003
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
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


def _read_log(process: subprocess.Popen[bytes]) -> str:
    """Whatever the child wrote, read back from the object that holds it.

    The log is an open file object over a ``mkstemp`` descriptor, not a path:
    ``fdopen`` names the object after the descriptor, an integer, so a
    ``Path(...)`` here raised before the child's own words could be shown —
    and the report about a stack that would not start became a TypeError.
    """
    log_file = getattr(process, "_log_file", None)
    if log_file is None:
        return ""
    try:
        log_file.flush()
        log_file.seek(0)
        return log_file.read().decode(errors="replace")
    except OSError, ValueError:
        return ""


def _wait_for(
    url: str, timeout: float = 180.0, process: subprocess.Popen[bytes] | None = None
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:  # noqa: S310  fixed localhost URL
                if response.status < 500:
                    return
        except URLError, TimeoutError:
            time.sleep(0.5)
        if process is not None and process.poll() is not None:
            output = _read_log(process)
            raise RuntimeError(
                f"{url} did not answer within {timeout}s; process exited "
                f"{process.returncode}:\n{output}"
            )
    # Timed out: capture whatever the process printed.
    output = _read_log(process) if process is not None else ""
    raise RuntimeError(f"{url} did not answer within {timeout}s:\n{output}")


async def _terminate_other_backends(database: str) -> None:
    """End every session but this one on a throwaway database.

    Before the schema is rebuilt, not after: ``reset_schema`` drops tables, and
    a previous capability's API can still be draining on a session whose locks
    would block that drop — the reset then waits on a process nobody owns.
    """
    engine = create_async_engine(url_for(database))
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid()"
            )
        )
    await engine.dispose()


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
    # The termination comes first: reset_schema drops tables, and a stale
    # session's locks would block that drop before any cleanup could run.
    asyncio.run(_terminate_other_backends(database))
    asyncio.run(reset_schema(url_for(database)))
    asyncio.run(_reset(database, seed_user))


def _spawn_api(environment: dict[str, str]) -> subprocess.Popen[bytes]:
    _fd, _ = tempfile.mkstemp(prefix="narrare-api-")
    log_file = os.fdopen(_fd, "w+b")
    proc = subprocess.Popen(  # noqa: S603  fixed argument list, this interpreter
        [sys.executable, "-m", "uvicorn", "app.api.main:app", "--port", str(API_PORT)],
        cwd=ROOT,
        env=environment,
        start_new_session=True,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    proc._log_file = log_file  # type: ignore[attr-defined]
    return proc


def _wait_for_free_port(port: int, timeout: float = 30.0) -> None:
    """Wait until nothing answers on a port a stack is about to bind.

    ``_wait_for`` cannot tell this stack's server from the previous one still
    shutting down: a leftover process on the port answers the health check
    while the freshly spawned one died on the bind, and every request then
    reaches a server whose database was just rebuilt underneath it. Waiting
    for the port to fall silent is what makes the health check mean "ours".
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(0.25)
    raise RuntimeError(f"port {port} still answers after {timeout}s: a previous stack did not stop")


def _stop(process: subprocess.Popen[bytes]) -> None:
    """End a whole process group: pnpm runs the dev server as a child."""
    if process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            process.wait(timeout=SHUTDOWN_TIMEOUT)
        except subprocess.TimeoutExpired:
            # A server that ignores SIGTERM must not outlive its module and
            # answer the next stack's health check with a dead database.
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait()
    log_file = getattr(process, "_log_file", None)
    if log_file is not None:
        log_file.close()


@dataclass
class Stack:
    """The running pieces, so a test can take one down and bring it back.

    An unreachable backend is a real condition of this product (a local service
    the user has not started). Stopping the real API is how a test produces it;
    nothing is simulated.
    """

    environment: dict[str, str]
    api: subprocess.Popen[bytes]
    web: subprocess.Popen[bytes]

    def stop_api(self) -> None:
        _stop(self.api)

    def start_api(self) -> None:
        self.api = _spawn_api(self.environment)
        _wait_for(f"http://127.0.0.1:{API_PORT}/openapi.json")


@contextmanager
def run_stack(
    *, database: str, seed_user: bool, env: dict[str, str] | None = None
) -> Generator[Stack]:
    # The handover between capability stacks: both ports must be silent before
    # this stack binds them, or the health check below would pass on a server
    # that belongs to the module before this one.
    _wait_for_free_port(API_PORT)
    _wait_for_free_port(WEB_PORT)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_prepare, database, seed_user).result()

    # Extra environment reaches the API only: a stack may point a provider at a
    # test-owned stand-in (the one boundary a fake may hold).
    environment = {**os.environ, "NARRE_DATABASE_URL": url_for(database), **(env or {})}
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise RuntimeError("pnpm is not on PATH")
    api_process = _spawn_api(environment)
    _fd2, _ = tempfile.mkstemp(prefix="narrare-web-")
    web_log = os.fdopen(_fd2, "w+b")
    web_process = subprocess.Popen(  # noqa: S603  fixed argument list, resolved path
        [pnpm, "dev"],
        cwd=ROOT / "web",
        env=environment,
        start_new_session=True,
        stdout=web_log,
        stderr=subprocess.STDOUT,
    )
    web_process._log_file = web_log  # type: ignore[attr-defined]
    stack = Stack(environment=environment, api=api_process, web=web_process)
    try:
        _wait_for(f"http://127.0.0.1:{API_PORT}/openapi.json", process=api_process)
        _wait_for(f"http://127.0.0.1:{WEB_PORT}", process=web_process)
        yield stack
    finally:
        # pnpm runs its server in a child process; kill the whole group or the
        # port stays bound after the test run. A test may have stopped the API
        # itself and failed before bringing it back: skip what is already gone.
        _stop(stack.web)
        _stop(stack.api)
