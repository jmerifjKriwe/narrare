"""Shared stack-orchestration seams and helpers — mode-agnostic.

Both stack modes build on these injectable seams so tests run without
docker and without spawning real processes (RULE-04/06 modularisation of
the former monolithic ``stack.py``):

- ``stack_containers`` — full app stack via ``docker-compose.release.yml``
  (non-default option); the API runs from the app image.
- ``stack_hybrid`` — PO ruling default: only the ``postgres`` service of
  ``docker-compose.dev.yml`` runs in compose; the API is a LOCAL uvicorn
  subprocess from the working tree (the benchmark measures current code).

Subprocess policy: the docker compose CLI only (subprocess — NEVER the
docker SDK), never a shell.

Port collision handling: free host ports are selected from the configured
scan range and injected through generated compose override files
(``ports: !override`` — Docker Compose v2.24+ tag semantics, already the
documented requirement).

Teardown verification (Global Constraints): after ``down -v
--remove-orphans``, containers, volumes, and networks whose name carries
the compose project prefix must all be gone.
"""

from __future__ import annotations

import socket
import subprocess  # nosec B404 — controlled compose CLI invocation, no shell
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
RELEASE_COMPOSE_FILE: Final[Path] = REPO_ROOT / "docker-compose.release.yml"
DEV_COMPOSE_FILE: Final[Path] = REPO_ROOT / "docker-compose.dev.yml"

_HEALTH_PATH: Final[str] = "/health"
_READY_PATH: Final[str] = "/ready"
HEALTH_TIMEOUT_S: Final[float] = 180.0
POLL_INTERVAL_S: Final[float] = 2.0
_PROBE_TIMEOUT_S: Final[float] = 5.0
# compose up includes image pulls; a local image build (build_image: auto,
# first run in a fresh clone) takes minutes on its own.
_SUBPROCESS_TIMEOUT_S: Final[float] = 900.0
_TIMEOUT_RC: Final[int] = 124
LOG_TAIL_LINES: Final[str] = "200"

# Database credentials shared by both modes; built from parts so no
# literal "user:password@host" secret-shaped string exists in source
# (gitleaks hygiene). Containers mode targets the release compose
# postgres (db ``narrare``), hybrid mode the dev compose postgres
# (db ``narrare_dev``) — hosts/ports/db names are per-mode.
_URL_SCHEME: Final[str] = "postgresql+asyncpg://"
_DB_USER: Final[str] = "narrare"
_DB_PASSWORD: Final[str] = "narrare"

_DEFAULT_OVERRIDE_DIR_SUFFIX: Final[str] = "-override"


class StackError(RuntimeError):
    """Raised when compose commands, process handling, or health waiting fail."""


@dataclass(frozen=True)
class CommandResult:
    """Captured outcome of one external command invocation."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    """Subprocess seam — production: ``run_subprocess``; tests: fakes."""

    def __call__(self, args: Sequence[str]) -> CommandResult: ...


def run_subprocess(
    args: Sequence[str], *, timeout_s: float = _SUBPROCESS_TIMEOUT_S
) -> CommandResult:
    """Run a command with captured output (never a shell)."""
    try:
        completed = subprocess.run(  # noqa: S603  # nosec B603 — fixed internal argv, no shell, no untrusted input
            list(args),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(tuple(args), _TIMEOUT_RC, "", f"timed out after {timeout_s}s")
    return CommandResult(tuple(args), completed.returncode, completed.stdout, completed.stderr)


class HealthProbe(Protocol):
    """Health-check seam — production: ``HttpxHealthProbe``; tests: fakes."""

    def healthy(self, base_url: str) -> bool: ...


class HttpxHealthProbe:
    """Probe the verified health endpoints (api-surface.md §5)."""

    def __init__(self, *, timeout_s: float = _PROBE_TIMEOUT_S) -> None:
        self._timeout_s = timeout_s

    def healthy(self, base_url: str) -> bool:
        try:
            with httpx.Client(timeout=self._timeout_s) as client:
                if client.get(f"{base_url}{_HEALTH_PATH}").status_code != 200:
                    return False
                return client.get(f"{base_url}{_READY_PATH}").status_code == 200
        except httpx.HTTPError:
            return False


class HealthWaiter:
    """Poll a health probe until it reports healthy — deadline-bounded.

    ``sleep``/``clock`` are injectable so tests run without real waiting.
    """

    def __init__(
        self,
        probe: Callable[[str], bool],
        *,
        timeout_s: float,
        interval_s: float,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._probe = probe
        self._timeout_s = timeout_s
        self._interval_s = interval_s
        self._sleep = sleep
        self._clock = clock

    def wait(self, base_url: str) -> None:
        """Block until the probe reports healthy; raise StackError at deadline."""
        deadline = self._clock() + self._timeout_s
        while not self._probe(base_url):
            if self._clock() >= deadline:
                raise StackError(
                    f"stack did not become healthy within {self._timeout_s:.0f}s "
                    f"at {base_url} (probed {_HEALTH_PATH} + {_READY_PATH})"
                )
            self._sleep(self._interval_s)


def select_free_port(low: int, high: int) -> int:
    """Return the first bindable host port in ``[low, high]`` (inclusive)."""
    for port in range(low, high + 1):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise StackError(f"no free port in [{low}, {high}]")


def default_override_dir(prefix: str) -> Path:
    """The conventional override directory for a compose project prefix."""
    return Path(tempfile.gettempdir()) / f"{prefix}{_DEFAULT_OVERRIDE_DIR_SUFFIX}"


def postgres_url(host: str, port: int, db: str) -> str:
    """Asyncpg DATABASE_URL for the stack's own postgres, built from parts."""
    return f"{_URL_SCHEME}{_DB_USER}:{_DB_PASSWORD}@{host}:{port}/{db}"


def compose_argv(
    prefix: str, compose_file: Path, *args: str, override: Path | None = None
) -> list[str]:
    """The compose CLI argv prefix for a project (optional override file)."""
    argv = ["docker", "compose", "-p", prefix, "-f", str(compose_file)]
    if override is not None:
        argv += ["-f", str(override)]
    return [*argv, *args]


def prefixed_leftovers(prefix: str, *, runner: CommandRunner) -> list[str]:
    """List docker resources whose name carries the project prefix.

    Raises ``StackError`` when any listing command fails — a failed
    listing must never be read as "no leftovers".
    """
    found: list[str] = []
    listings: tuple[tuple[str, ...], ...] = (
        ("ps", "-a", "--format", "{{.Names}}"),
        ("volume", "ls", "--format", "{{.Name}}"),
        ("network", "ls", "--format", "{{.Name}}"),
    )
    for tail in listings:
        result = runner(["docker", *tail])
        if result.returncode != 0:
            raise StackError(
                f"resource listing failed (rc={result.returncode}): "
                f"{' '.join(result.args)}\n{result.stderr}"
            )
        found += [name for name in result.stdout.splitlines() if name.startswith(prefix)]
    return found
