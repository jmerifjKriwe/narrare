"""A real stack for capability E2E tests: own database, real API, real web app.

Nothing here is a fake. The browser, the HTTP API and Postgres are the ones the
product runs; only the LLM provider will ever be replaced, and only at its own
boundary.

Each capability's ``e2e/conftest.py`` wraps :func:`run_stack` in a module-scoped
fixture. The API and its database are what the module scope is for: the API
serves one database, and the next capability's schema rebuild must not reach a
server the module before it still drives. The web server is the exception — it
is stateless and the slowest piece to start, so one Vite process serves every
stack in a pytest process (:func:`stop_shared_web` ends it at session teardown).

Under ``pytest-xdist`` every worker is a process of its own, so each owns one
shared Vite and one port pair: the configured pair moved by
``WORKER_PORT_SPACING`` per worker (``-n 2`` gives gw0 8000/3100 and gw1
8010/3110).

``NARRE_E2E_ATTACH`` points the same suites at an instance that is already
running — the container image, which serves the shell and the API on one origin
where a development stack serves them on two. Nothing is spawned and nothing is
reset, because the database under test is the artefact's own: the release gate
runs a suite against a virgin instance and reads what that first boot produced.
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

E2E_SECRET_KEY = "W1Ap61h7AxVPB6qFGKd5SSVMnN5mXFwFAzkA1wEXT_M="
"""A fixed Fernet key for every E2E stack's key store.

Public on purpose: it is test infrastructure, not a secret — it exists so a
profile's ``api_key`` column deterministically holds Fernet ciphertext (and a
restored row stays decryptable across runs), never so that it hides anything.
"""


# Ports and shutdown grace are configuration: a second stack, or a busy port on
# this machine, must not need a code edit. The defaults are the ones the docs use.


def _worker_index() -> int:
    """This process's pytest-xdist worker number, or 0 without xdist.

    ``pytest-xdist`` names each worker ``gw0``, ``gw1``, … in its environment;
    the controller and a serial run have no such variable.
    """
    worker = environ.get("PYTEST_XDIST_WORKER", "")
    if not worker:
        return 0
    if not worker.startswith("gw") or not worker[2:].isdigit():
        raise RuntimeError(f"PYTEST_XDIST_WORKER={worker!r} is not a worker name like 'gw0'")
    return int(worker[2:])


WORKER_PORT_SPACING = 10
"""How far apart two workers' port pairs sit.

Ten, not one: the pair stays recognisable (8000/3100, 8010/3110, …) and a
neighbouring port another service happens to hold is less likely to be in the
way.
"""

_WORKER_INDEX = _worker_index()

API_PORT = int(environ.get("NARRE_E2E_API_PORT", "8000")) + _WORKER_INDEX * WORKER_PORT_SPACING
WEB_PORT = int(environ.get("NARRE_E2E_WEB_PORT", "3100")) + _WORKER_INDEX * WORKER_PORT_SPACING

_ATTACH_URL = environ.get("NARRE_E2E_ATTACH", "").strip().rstrip("/")

ATTACH = bool(_ATTACH_URL)
"""A running instance to drive instead of spawning one; empty means spawn."""

if ATTACH and _WORKER_INDEX > 0:
    # An attached instance has one origin and one database, and no stack of
    # its own to give a worker — parallel workers would race in that one
    # database. Fail at import, before a test reports a phantom pass.
    raise RuntimeError(
        "NARRE_E2E_ATTACH drives one instance and one database; it runs"
        " serially. Run the suite with -n 0 (`just test-e2e` does this for an"
        " attached run)."
    )

# One origin when attached, as the image serves it: the shell and the API answer
# on the same port, so a suite that named two would test a shape the product
# does not have in production.
API_URL = _ATTACH_URL or f"http://127.0.0.1:{API_PORT}"
WEB_URL = _ATTACH_URL or f"http://127.0.0.1:{WEB_PORT}"
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
    # Derive the table list from the models so it cannot drift from the schema
    # the way the previous hard-coded list did (it had fallen to 5 tables).
    from app.kernel.db.base import Base
    from app.kernel.db.migrate import register_models

    register_models()
    tables = ", ".join(sorted(Base.metadata.tables))
    engine = create_async_engine(url_for(database))
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))
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


async def _seed_local_user(database_url: str, seed_user: bool) -> None:
    """The one precondition an attached instance cannot get from ``_prepare``.

    There is no reset: the attached database belongs to the artefact, and
    truncating it would destroy the state under test. Only the local user row
    is added, and only when the caller asked for an installed instance.
    """
    if not seed_user:
        return
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text("INSERT INTO users (id, created_at) VALUES (:id, now()) ON CONFLICT DO NOTHING"),
            {"id": LOCAL_USER_ID},
        )
    await engine.dispose()


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


def _web_environment() -> dict[str, str]:
    """The dev server's environment, with this worker's ports pinned.

    ``os.environ`` still holds the pair the run was started with; under
    ``pytest-xdist`` the worker's pair is shifted (see ``API_PORT``), and a
    forwarded stale value would bind the port the neighbour already owns.
    The cache flag is the stack's contract (#634) and cannot be switched off.
    """
    return {
        **os.environ,
        "NARRE_E2E_API_PORT": str(API_PORT),
        "NARRE_E2E_WEB_PORT": str(WEB_PORT),
        "NARRE_E2E_NO_HTTP_CACHE": "1",
    }


def _spawn_web() -> subprocess.Popen[bytes]:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise RuntimeError("pnpm is not on PATH")
    _fd, _ = tempfile.mkstemp(prefix="narrare-web-")
    log_file = os.fdopen(_fd, "w+b")
    proc = subprocess.Popen(  # noqa: S603  fixed argument list, resolved path
        [pnpm, "dev"],
        cwd=ROOT / "web",
        env=_web_environment(),
        start_new_session=True,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    proc._log_file = log_file  # type: ignore[attr-defined]
    return proc


_shared_web: subprocess.Popen[bytes] | None = None


def _shared_web_process() -> subprocess.Popen[bytes]:
    """The one Vite dev server this pytest process drives, started on demand.

    Restarting a stack must not restart it: the dev server carries no state a
    test asserts on, and every capability module after the first would
    otherwise pay Vite's cold start again. :func:`stop_shared_web` is its only
    stopper, called once by the session teardown.
    """
    global _shared_web
    if _shared_web is not None and _shared_web.poll() is None:
        return _shared_web
    if _shared_web is not None:
        # A server that died: ``_stop`` skips the signal (the process is gone)
        # and closes its log descriptor, which the replacement would leak.
        _stop(_shared_web)
        _shared_web = None
    _wait_for_free_port(WEB_PORT)
    process = _spawn_web()
    _wait_for(WEB_URL, process=process)
    _shared_web = process
    return process


def stop_shared_web() -> None:
    """End the shared dev server, if one was started."""
    global _shared_web
    if _shared_web is None:
        return
    _stop(_shared_web)
    _shared_web = None


@dataclass
class Stack:
    """The running pieces, so a test can take one down and bring it back.

    An unreachable backend is a real condition of this product (a local service
    the user has not started). Stopping the real API is how a test produces it;
    nothing is simulated.
    """

    environment: dict[str, str]
    # None when this stack is attached to a running instance: there is no
    # process to signal, and saying so beats a TypeError from a None.
    api: subprocess.Popen[bytes] | None
    # Shared across every stack in this pytest process; the session teardown
    # ends it (``stop_shared_web``), never one module's end.
    web: subprocess.Popen[bytes] | None
    # Hebel 2: the database this stack owns, so a reused stack can reset it
    # between modules and keep test isolation without restarting the API.
    database: str = ""
    seed_user: bool = False

    def stop_api(self) -> None:
        if self.api is None:
            raise RuntimeError(
                "this stack is attached to a running instance; the API is the"
                " container's process and cannot be stopped from the test"
            )
        _stop(self.api)

    def start_api(self) -> None:
        if self.api is None:
            raise RuntimeError(
                "this stack is attached to a running instance; the API is the"
                " container's process and cannot be restarted from the test"
            )
        self.api = _spawn_api(self.environment)
        _wait_for(f"{API_URL}/openapi.json")


def _environment(database: str, env: dict[str, str] | None) -> dict[str, str]:
    """The children's environment, with the stack's cache contract last.

    A caller's extras choose a provider stand-in and are merged over the
    pinned keys; the cache flag is not a provider boundary, so a caller cannot
    switch it off (#634).
    """
    if ATTACH:
        # The instance brought its own configuration; a test's extras still win.
        return {**os.environ, **(env or {})}
    return {
        **os.environ,
        "NARRE_DATABASE_URL": url_for(database),
        "NARRE_SECRET_KEY": E2E_SECRET_KEY,
        "NARRE_KEYRING": "off",
        **(env or {}),
        # Vite otherwise answers transformed modules with no-cache, and each of
        # the sweep's hard navigations revalidates the whole dev graph with
        # 304s; Chromium drops cached module bodies after enough of them
        # (net::ERR_INSUFFICIENT_RESOURCES) and the page never renders (#634).
        # no-store keeps every E2E load a fresh 200; `just dev-web` keeps the
        # default, so a developer's reloads still cache. Last, not before the
        # extras: a caller cannot switch the stack's contract off.
        "NARRE_E2E_NO_HTTP_CACHE": "1",
    }


@contextmanager
def run_stack(
    *, database: str, seed_user: bool, env: dict[str, str] | None = None
) -> Generator[Stack]:
    # The handover between capability stacks: both ports must be silent before
    # this stack binds them, or the health check below would pass on a server
    # that belongs to the module before this one.
    if ATTACH:
        database_url = environ.get("NARRE_DATABASE_URL", "")
        if not database_url:
            raise RuntimeError(
                "NARRE_E2E_ATTACH needs NARRE_DATABASE_URL: the attached"
                " instance's database is where the preconditions are seeded"
            )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, _seed_local_user(database_url, seed_user)).result()
        yield Stack(
            environment=_environment(database, env),
            api=None,
            web=None,
            database=database,
            seed_user=seed_user,
        )
        return

    _wait_for_free_port(API_PORT)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_prepare, database, seed_user).result()

    # A caller's extras point a provider at a test-owned stand-in, the one
    # boundary a fake may hold. Everything else is the stack's own: the Fernet
    # tier runs under this test key (never a developer's real OS keychain) and
    # the cache flag stays on, so no capability can bring the 304s back.
    environment = _environment(database, env)
    api_process = _spawn_api(environment)
    try:
        web_process = _shared_web_process()
    except BaseException:
        # A dev server that would not start must not leave the API it was meant
        # to serve behind.
        _stop(api_process)
        raise
    stack = Stack(
        environment=environment,
        api=api_process,
        web=web_process,
        database=database,
        seed_user=seed_user,
    )
    try:
        _wait_for(f"{API_URL}/openapi.json", process=api_process)
        _wait_for(WEB_URL, process=web_process)
        yield stack
    finally:
        # pnpm runs its server in a child process; kill the whole group or the
        # port stays bound after the test run. A test may have stopped the API
        # itself and failed before bringing it back: skip what is already gone.
        # The web server is shared across the process (see ``stop_shared_web``)
        # and outlives this module on purpose.
        if stack.api is not None:
            _stop(stack.api)


# Hebel 2 pilot: a worker-process-wide cache of capability stacks. A capability's
# API and database are started once per worker and reused by every test module of
# that capability; the port handover happens when a different capability asks.
# Nothing here is stopped per module — teardown is session-wide (see
# ``stop_capability_stacks``), so a crashed test can poison later modules of the
# same capability; that is the pilot's known risk.

_CAPABILITY_STACKS: dict[str, Stack] = {}


def _start_capability_stack(
    capability: str, *, database: str, seed_user: bool, env: dict[str, str] | None
) -> Stack:
    """Spawn one stack for ``capability`` and cache it. Caller holds the lock."""
    if ATTACH:
        database_url = environ.get("NARRE_DATABASE_URL", "")
        if not database_url:
            raise RuntimeError(
                "NARRE_E2E_ATTACH needs NARRE_DATABASE_URL: the attached"
                " instance's database is where the preconditions are seeded"
            )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, _seed_local_user(database_url, seed_user)).result()
        stack = Stack(
            environment=_environment(database, env),
            api=None,
            web=None,
            database=database,
            seed_user=seed_user,
        )
        _CAPABILITY_STACKS[capability] = stack
        return stack

    _wait_for_free_port(API_PORT)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_prepare, database, seed_user).result()

    environment = _environment(database, env)
    api_process = _spawn_api(environment)
    try:
        web_process = _shared_web_process()
    except BaseException:
        _stop(api_process)
        raise
    stack = Stack(
        environment=environment,
        api=api_process,
        web=web_process,
        database=database,
        seed_user=seed_user,
    )
    try:
        _wait_for(f"{API_URL}/openapi.json", process=api_process)
        _wait_for(WEB_URL, process=web_process)
    except BaseException:
        _stop(api_process)
        raise
    _CAPABILITY_STACKS[capability] = stack
    return stack


def _reset_cached_stack(database: str, seed_user: bool) -> None:
    """Reset a reused stack's database between test modules (Hebel 2).

    Terminates lingering backends (so TRUNCATE can acquire its lock) and then
    truncates and re-seeds. Runs in a worker thread: pytest-asyncio keeps a
    session loop running, and ``asyncio.run`` refuses to start a second one
    in the same thread.
    """
    asyncio.run(_terminate_other_backends(database))
    asyncio.run(_reset(database, seed_user))


def acquire_stack(
    capability: str, *, database: str, seed_user: bool, env: dict[str, str] | None = None
) -> Stack:
    """Return the running stack for ``capability``, starting it on first use.

    A different capability's stack is stopped first so the port is free; the
    same capability's stack is reused for the rest of the worker process.
    """
    # Hand over the port if another capability currently owns it.
    for other in list(_CAPABILITY_STACKS):
        if other != capability:
            other_stack = _CAPABILITY_STACKS.pop(other)
            if other_stack.api is not None:
                _stop(other_stack.api)

    cached = _CAPABILITY_STACKS.get(capability)
    if cached is not None and (cached.api is None or cached.api.poll() is None):
        # Hebel 2 reuses the stack (and its database) across modules in one
        # worker. Reset the data between modules so tests keep their isolation:
        # every module expects a clean database, as it had before Hebel 2.
        if not ATTACH and cached.database:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(_reset_cached_stack, cached.database, cached.seed_user).result()
        return cached
    if cached is not None:
        # Died without a clean teardown: drop the stale entry.
        del _CAPABILITY_STACKS[capability]
    return _start_capability_stack(capability, database=database, seed_user=seed_user, env=env)


def stop_capability_stacks() -> None:
    """End every cached capability stack. Called at session teardown."""
    for stack in list(_CAPABILITY_STACKS.values()):
        if stack.api is not None:
            _stop(stack.api)
    _CAPABILITY_STACKS.clear()
