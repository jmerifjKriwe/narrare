"""Hybrid stack mode (PO ruling) — dev-compose postgres + LOCAL uvicorn API.

Default stack mode: only the ``postgres`` service of
``docker-compose.dev.yml`` runs in docker (own compose project carrying
the configured prefix); the API is a LOCAL uvicorn subprocess launched
from the working tree — the benchmark measures current code, with no
image build (that is why hybrid replaced the image-based containers mode
as the default; ``stack_containers`` remains the non-default option).

Up sequence (``HybridStack.up()``):

1. Select a free host port for postgres from the configured scan range
   and inject it through a generated compose override file
   (``ports: !override`` — replaces the dev file's fixed ``5432:5432``
   mapping; Docker Compose v2.24+ tag semantics, same mechanism as the
   containers mode).
2. ``docker compose -p <prefix> -f docker-compose.dev.yml up -d postgres``.
3. Wait for postgres readiness by TCP-polling the mapped host port.
   Chosen over ``pg_isready``-via-``compose exec`` because it is both
   robust (postgres accepts connections only once it is ready to serve)
   and simple (no container-name resolution, no exec plumbing), and it
   is a fully injectable seam so tests run without docker.
4. Spawn ``uv run uvicorn narrare._app.main:app --host 127.0.0.1 --port
   <api_port>`` (cwd ``apps/api``, per the ``just dev-api`` precedent)
   with ``DATABASE_URL`` pointing at the prefixed postgres via its
    mapped host port (``postgresql+asyncpg://…`` — the exact scheme
    ``Settings.database_url`` and the lifespan's Alembic migration step
    read from the environment). All other variables are inherited plus
    the operator-plane pins (finding #7 — ``stack_operator_env``),
    except ``NARRARE_E2E_TEST``, which is pinned to
    ``false``: a real env var beats any ``.env`` file in
    pydantic-settings precedence, so a repo-root ``.env`` with
    ``NARRARE_E2E_TEST=1`` cannot silently switch the API to TestModel
    (rehearsal finding #6). stdout/stderr go to a run-scoped log file
    (``<tmpdir>/<prefix>-uvicorn/uvicorn.log``) for failure diagnosis;
    a health-wait failure attaches the log tail to the error.
5. Poll ``/health`` + ``/ready`` on the API port (the shared
   ``HealthWaiter``); readiness includes the DB ``SELECT 1``, and the
   app's lifespan runs pending Alembic migrations before serving — so a
   green poll means migrations applied.
6. Honesty gate (``ensure_not_e2e_test_mode``): after the health-wait,
   the captured log is scanned for the lifespan's
   ``e2e_test_mode_active`` marker — if the API still came up in E2E
   test mode (TestModel), ``up()`` refuses before any LLM work runs;
   measuring canned output is invalid (rehearsal finding #6).

Teardown (``HybridStack.teardown()``): terminate the uvicorn process
GROUP first (spawned with ``start_new_session=True``; SIGTERM, grace
deadline, then SIGKILL — children never outlive the stack), then
``compose down -v --remove-orphans``, then residue verification:
prefixed docker resources gone AND no live uvicorn child (process exited
or its API port refuses connections).

Facts honesty: hybrid mode has NO app image, so ``facts()`` records the
dev-compose SHA-256 plus runtime identity pairs — ``mode``,
``uvicorn_pid``, ``api_port`` — in the manifest's stack-facts pairs slot
(see ``StackFacts``). Facts requested before ``up()`` raise; nothing is
fabricated.
"""

from __future__ import annotations

import hashlib
import os
import signal
import socket
import subprocess  # nosec B404 — controlled uvicorn CLI invocation, no shell
import tempfile
import time
from pathlib import Path
from typing import IO, TYPE_CHECKING, Final, Protocol

from benchmark.stack_common import (
    DEV_COMPOSE_FILE,
    REPO_ROOT,
    StackError,
    compose_argv,
    postgres_url,
    prefixed_leftovers,
)
from benchmark.stack_e2e_guard import ensure_not_e2e_test_mode
from benchmark.stack_operator_env import operator_env_pins

if TYPE_CHECKING:
    from collections.abc import Callable

    from benchmark.config_schemas import BenchmarkConfig
    from benchmark.stack_common import CommandRunner, HealthWaiter

POSTGRES_OVERRIDE_FILE_NAME: Final[str] = "benchmark-postgres-override.yml"

_POSTGRES_SERVICE: Final[str] = "postgres"
_PG_CONTAINER_PORT: Final[int] = 5432
_HYBRID_DB_NAME: Final[str] = "narrare_dev"  # dev compose POSTGRES_DB
_API_HOST: Final[str] = "127.0.0.1"
_APPS_API_DIR: Final[Path] = REPO_ROOT / "apps" / "api"
_LOG_DIR_SUFFIX: Final[str] = "-uvicorn"
_UVICORN_LOG_NAME: Final[str] = "uvicorn.log"
_UVICORN_MODULE: Final[str] = "narrare._app.main:app"
_UVICORN_RUNNER: Final[str] = "uv"

_PG_WAIT_TIMEOUT_S: Final[float] = 60.0
_PG_POLL_INTERVAL_S: Final[float] = 0.5
_TERMINATE_GRACE_S: Final[float] = 10.0
_LOG_TAIL_CHARS: Final[int] = 4000


def default_uvicorn_log_dir(prefix: str) -> Path:
    """The conventional run-scoped uvicorn log directory for a prefix."""
    return Path(tempfile.gettempdir()) / f"{prefix}{_LOG_DIR_SUFFIX}"


class ManagedProcess(Protocol):
    """The process handle seam — structural: ``subprocess.Popen`` fits."""

    @property
    def pid(self) -> int: ...

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class ProcessSpawner(Protocol):
    """Process-creation seam — production: ``spawn_process_group``; tests: fakes."""

    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        stdout: IO[bytes],
        stderr: IO[bytes],
    ) -> ManagedProcess: ...


class ProcessTerminator(Protocol):
    """Process-kill seam — production: ``terminate_process_group``; tests: fakes."""

    def __call__(self, process: ManagedProcess, /, *, grace_s: float) -> None: ...


class PgWaiter(Protocol):
    """Postgres-readiness seam — production: ``wait_tcp``; tests: fakes."""

    def __call__(self, host: str, port: int, /) -> None: ...


class TcpProber(Protocol):
    """Port-liveness seam — production: ``tcp_accepts``; tests: fakes."""

    def __call__(self, host: str, port: int, /) -> bool: ...


def spawn_process_group(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout: IO[bytes],
    stderr: IO[bytes],
) -> ManagedProcess:
    """Start the uvicorn subprocess in its OWN process group (no shell).

    ``start_new_session=True`` puts the child into a fresh session so the
    whole group can be signalled at teardown — children of the child
    never outlive the stack.
    """
    return subprocess.Popen(  # noqa: S603  # nosec B603 — fixed internal argv, no shell
        argv,
        cwd=cwd,
        env=env,
        stdout=stdout,
        stderr=stderr,
        start_new_session=True,
    )


def terminate_process_group(process: ManagedProcess, *, grace_s: float) -> None:
    """SIGTERM the process group, wait ``grace_s``, then SIGKILL stragglers."""
    if process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except ProcessLookupError:
        return  # process (group) already gone — nothing to terminate
    try:
        process.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait()


def wait_tcp(
    host: str,
    port: int,
    *,
    timeout_s: float = _PG_WAIT_TIMEOUT_S,
    interval_s: float = _PG_POLL_INTERVAL_S,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Block until a TCP connection to ``host:port`` succeeds — deadline-bounded.

    Postgres readiness proxy: the server accepts connections only once it
    can serve them, so a successful connect means ready (compose's own
    ``pg_isready`` healthcheck has the same semantics).
    """
    deadline = clock() + timeout_s
    while True:
        with socket.socket() as sock:
            if sock.connect_ex((host, port)) == 0:
                return
        if clock() >= deadline:
            raise StackError(
                f"postgres did not accept connections within {timeout_s:.0f}s at {host}:{port}"
            )
        sleep(interval_s)


def tcp_accepts(host: str, port: int) -> bool:
    """Whether a TCP connection to ``host:port`` succeeds right now."""
    with socket.socket() as sock:
        return sock.connect_ex((host, port)) == 0


def _log_tail(path: Path) -> str:
    """Last characters of the uvicorn log, for failure diagnosis."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[-_LOG_TAIL_CHARS:]
    except OSError:
        return "(uvicorn log unavailable)"


class HybridStack:
    """Bring up, health-check, and tear down the hybrid (local API) stack."""

    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        runner: CommandRunner,
        waiter: HealthWaiter,
        port_selector: Callable[[int, int], int],
        override_dir: Path,
        spawner: ProcessSpawner,
        terminator: ProcessTerminator,
        pg_waiter: PgWaiter,
        tcp_prober: TcpProber,
        uvicorn_log_dir: Path,
    ) -> None:
        self._config = config
        self._prefix = config.stack.project_name
        self._runner = runner
        self._waiter = waiter
        self._port_selector = port_selector
        self._override_dir = override_dir
        self._spawn = spawner
        self._terminator = terminator
        self._pg_waiter = pg_waiter
        self._tcp_prober = tcp_prober
        self._uvicorn_log_dir = uvicorn_log_dir
        self._log_path = uvicorn_log_dir / _UVICORN_LOG_NAME
        self._process: ManagedProcess | None = None
        self._api_port: int | None = None
        self._pg_port: int | None = None

    def up(self) -> str:
        """Start postgres + the local API; return the API base URL."""
        low = self._config.stack.port_range_low
        high = self._config.stack.port_range_high
        pg_port = self._port_selector(low, high)
        override = self._write_pg_override(pg_port)
        result = self._runner(self._compose("up", "-d", _POSTGRES_SERVICE, override=override))
        if result.returncode != 0:
            raise StackError(
                f"compose up failed (rc={result.returncode}):\n"
                f"{' '.join(result.args)}\n{result.stdout}\n{result.stderr}"
            )
        self._pg_waiter(_API_HOST, pg_port)
        api_port = self._port_selector(low, high)
        self._start_uvicorn(pg_port, api_port)
        base_url = f"http://{_API_HOST}:{api_port}"
        try:
            self._waiter.wait(base_url)
        except StackError as exc:
            raise StackError(
                f"{exc}\n--- uvicorn log tail ({self._log_path}) ---\n{_log_tail(self._log_path)}"
            ) from exc
        ensure_not_e2e_test_mode(self._log_path)
        return base_url

    def teardown(self, *, verify: bool = True) -> None:
        """Kill uvicorn FIRST, then compose down, then verify residue-free."""
        process = self._process
        if process is not None:
            self._terminator(process, grace_s=_TERMINATE_GRACE_S)
        result = self._runner(self._compose("down", "-v", "--remove-orphans"))
        if result.returncode != 0:
            raise StackError(
                f"compose down failed (rc={result.returncode}):\n"
                f"{' '.join(result.args)}\n{result.stdout}\n{result.stderr}"
            )
        if verify:
            leftovers = prefixed_leftovers(self._prefix, runner=self._runner)
            if leftovers:
                raise StackError(
                    f"teardown left resources behind (prefix {self._prefix!r}): {leftovers}"
                )
            if process is not None and self._uvicorn_alive(process):
                raise StackError(
                    f"teardown left the uvicorn subprocess running (pid {process.pid})"
                )

    def is_up(self) -> bool:
        """Whether the hybrid stack currently serves: live process + open API port."""
        process = self._process
        if process is None or self._api_port is None:
            return False
        return process.poll() is None and self._tcp_prober(_API_HOST, self._api_port)

    def facts(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        """Dev-compose SHA-256 + runtime identity pairs (mode/pid/api_port).

        Hybrid mode has no app image; instead of digests the manifest's
        stack-facts pairs record the runtime identity — see module
        docstring. Facts before ``up()`` would be fabricated facts → raise.
        """
        process = self._process
        if process is None or self._api_port is None:
            raise StackError("stack facts requested before up() — no runtime identity yet")
        digest = hashlib.sha256(DEV_COMPOSE_FILE.read_bytes()).hexdigest()
        pairs = (
            ("mode", "hybrid"),
            ("uvicorn_pid", str(process.pid)),
            ("api_port", str(self._api_port)),
        )
        return digest, tuple(sorted(pairs))

    def _start_uvicorn(self, pg_port: int, api_port: int) -> None:
        """Spawn the API subprocess from the working tree (PO ruling)."""
        self._uvicorn_log_dir.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "DATABASE_URL": postgres_url(_API_HOST, pg_port, _HYBRID_DB_NAME),
            # Rehearsal finding #6: a real env var beats any ``.env`` file
            # in pydantic-settings precedence, so pinning ``false`` here
            # overrides a repo-root ``.env`` with ``NARRARE_E2E_TEST=1`` —
            # otherwise CoreSettings (ADR-071, lru-cached at startup)
            # silently switches ALL LLM providers to TestModel.
            "NARRARE_E2E_TEST": "false",
            **operator_env_pins(self._config.llm),
        }
        argv = [
            _UVICORN_RUNNER,
            "run",
            "uvicorn",
            _UVICORN_MODULE,
            "--host",
            _API_HOST,
            "--port",
            str(api_port),
        ]
        # "wb" (truncate), not "ab": the log is run-scoped by design and
        # the E2E guard scans the WHOLE file — stale markers from earlier
        # runs must not false-trigger the refusal (finding #6b).
        with self._log_path.open("wb") as log:
            process = self._spawn(argv, cwd=_APPS_API_DIR, env=env, stdout=log, stderr=log)
        self._process = process
        self._api_port = api_port
        self._pg_port = pg_port

    def _uvicorn_alive(self, process: ManagedProcess) -> bool:
        """Live = not exited AND the API port still accepts connections."""
        if process.poll() is not None:
            return False
        if self._api_port is None:
            return True
        return self._tcp_prober(_API_HOST, self._api_port)

    def _write_pg_override(self, port: int) -> Path:
        """Write the postgres port override (``ports: !override`` — v2.24+)."""
        self._override_dir.mkdir(parents=True, exist_ok=True)
        path = self._override_dir / POSTGRES_OVERRIDE_FILE_NAME
        lines = [
            "services:",
            f"  {_POSTGRES_SERVICE}:",
            "    ports: !override",
            f'      - "{_API_HOST}:{port}:{_PG_CONTAINER_PORT}"',
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _compose(self, *args: str, override: Path | None = None) -> list[str]:
        return compose_argv(self._prefix, DEV_COMPOSE_FILE, *args, override=override)
