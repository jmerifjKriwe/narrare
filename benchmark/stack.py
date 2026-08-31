"""Compose stack orchestration for the KB benchmark runner (PO decision F1=B).

Self-managed stack: the runner brings up its own Narrare stack via the
docker compose CLI (subprocess — NEVER the docker SDK) and tears it down
residue-free. The repo's ``docker-compose.release.yml`` is the only
compose file defining the full application (the dev file is DBs-only);
the app image exposes the FastAPI API on container port 8000.

Port collision handling: a free host port is selected from the configured
scan range and injected through a generated compose override file
(``ports: !override`` — replaces the release file's fixed ``3000:3000``
mapping; requires Docker Compose v2.24+, already the documented release
requirement). The same override pins ``DATABASE_URL`` to the stack's own
postgres service, so the app never reaches a host database.

Health waiting polls the verified endpoints from
``benchmark/docs/api-surface.md`` §5: ``GET /health`` (liveness) then
``GET /ready`` (readiness incl. DB ``SELECT 1``).

Teardown verification (Global Constraints): after ``down -v
--remove-orphans``, containers, volumes, and networks whose name carries
the compose project prefix must all be gone.

All subprocess I/O and health probing go through injectable seams
(``CommandRunner``, ``HealthWaiter``) so tests run without docker.
"""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess  # nosec B404 — controlled compose CLI invocation, no shell
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, cast

import httpx

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from benchmark.config_schemas import BenchmarkConfig

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
RELEASE_COMPOSE_FILE: Final[Path] = REPO_ROOT / "docker-compose.release.yml"
OVERRIDE_FILE_NAME: Final[str] = "benchmark-compose-override.yml"

_API_CONTAINER_PORT: Final[int] = 8000
_HEALTH_PATH: Final[str] = "/health"
_READY_PATH: Final[str] = "/ready"
_HEALTH_TIMEOUT_S: Final[float] = 180.0
_POLL_INTERVAL_S: Final[float] = 2.0
_PROBE_TIMEOUT_S: Final[float] = 5.0
_SUBPROCESS_TIMEOUT_S: Final[float] = 600.0  # compose up includes image pulls
_TIMEOUT_RC: Final[int] = 124
_LOG_TAIL_LINES: Final[str] = "200"

# Built from parts so no literal "user:password@host" secret-shaped string
# exists in source (gitleaks hygiene); values match the release compose
# postgres defaults (DB_USER/DB_PASSWORD/DB_NAME = narrare).
_DB_URL_TEMPLATE: Final[str] = "postgresql+asyncpg://{user}:{password}@{host}:5432/{db}"
_DB_USER: Final[str] = "narrare"
_DB_PASSWORD: Final[str] = "narrare"
_DB_NAME: Final[str] = "narrare"
_DB_HOST: Final[str] = "postgres"  # compose service hostname


class StackError(RuntimeError):
    """Raised when compose commands or health waiting fail."""


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


class HealthProbe(Protocol):
    """Health-check seam — production: ``HttpxHealthProbe``; tests: fakes."""

    def healthy(self, base_url: str) -> bool: ...


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


def parse_image_digests(json_text: str) -> tuple[tuple[str, str], ...]:
    """``docker compose images --format json`` → sorted (service, digest) pairs.

    Row key: ``Service`` when present, else ``Repository``. Row value:
    ``Digest``, falling back to ``ID`` for locally built images; rows
    carrying neither a key nor a value are skipped — nothing is
    fabricated. Duplicate pairs (several containers per image) collapse.
    """
    try:
        loaded: object = json.loads(json_text) if json_text.strip() else []
    except json.JSONDecodeError as exc:
        raise StackError(f"compose images: output is not JSON ({exc})") from exc
    if not isinstance(loaded, list):
        raise StackError(f"compose images: expected a JSON list, got {type(loaded).__name__}")
    pairs: set[tuple[str, str]] = set()
    for row in cast("list[object]", loaded):
        if not isinstance(row, dict):
            continue
        entry = cast("dict[str, object]", row)
        key = entry.get("Service") or entry.get("Repository")
        value = entry.get("Digest") or entry.get("ID")
        if isinstance(key, str) and key and isinstance(value, str) and value:
            pairs.add((key, value))
    return tuple(sorted(pairs))


class StackManager:
    """Bring up, health-check, and tear down the benchmark compose stack."""

    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        runner: CommandRunner | None = None,
        probe: HealthProbe | None = None,
        waiter: HealthWaiter | None = None,
        port_selector: Callable[[int, int], int] = select_free_port,
        override_dir: Path | None = None,
    ) -> None:
        self._config = config
        self._prefix = config.stack.project_name
        self._runner: CommandRunner = runner or run_subprocess
        if waiter is None:
            probe_impl = probe or HttpxHealthProbe()
            waiter = HealthWaiter(
                probe_impl.healthy,
                timeout_s=_HEALTH_TIMEOUT_S,
                interval_s=_POLL_INTERVAL_S,
            )
        self._waiter = waiter
        self._port_selector = port_selector
        self._override_dir = override_dir or (
            Path(tempfile.gettempdir()) / f"{self._prefix}-override"
        )

    def up(self) -> str:
        """Start the stack; return the API base URL it became healthy on."""
        base_url = self._config.api.base_url
        port: int | None = None
        if base_url is None:
            low = self._config.stack.port_range_low
            high = self._config.stack.port_range_high
            port = self._port_selector(low, high)
            base_url = f"http://127.0.0.1:{port}"
        override = self._write_override(port)
        result = self._runner(self._compose("up", "-d", override=override))
        if result.returncode != 0:
            raise StackError(
                f"compose up failed (rc={result.returncode}):\n"
                f"{' '.join(result.args)}\n{result.stdout}\n{result.stderr}"
            )
        try:
            assert base_url is not None
            self._waiter.wait(base_url)
        except StackError as exc:
            logs = self._runner(
                self._compose("logs", "--no-color", "--tail", _LOG_TAIL_LINES, override=override)
            )
            raise StackError(
                f"{exc}\n--- compose logs (rc={logs.returncode}) ---\n{logs.stdout}\n{logs.stderr}"
            ) from exc
        return base_url

    def teardown(self, *, verify: bool = True) -> None:
        """Remove the stack (containers, volumes, orphans) and verify residue-free."""
        result = self._runner(self._compose("down", "-v", "--remove-orphans"))
        if result.returncode != 0:
            raise StackError(
                f"compose down failed (rc={result.returncode}):\n"
                f"{' '.join(result.args)}\n{result.stdout}\n{result.stderr}"
            )
        if verify:
            leftovers = self._prefixed_resources()
            if leftovers:
                raise StackError(
                    f"teardown left resources behind (prefix {self._prefix!r}): {leftovers}"
                )

    def is_up(self) -> bool:
        """Whether any service of the project currently runs."""
        result = self._runner(self._compose("ps", "--status", "running", "--format", "{{.Name}}"))
        return result.returncode == 0 and bool(result.stdout.strip())

    def facts(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        """Stack identity facts for the run manifest (Task 14/15 wiring).

        Returns ``(compose_sha256, image_digests)``: the SHA-256 of the
        release compose file, and per-service repository digests from
        ``docker compose images --format json`` (the runner assembles the
        ``StackFacts`` record; the API version payload comes from the
        client, not the stack).
        """
        digest = hashlib.sha256(RELEASE_COMPOSE_FILE.read_bytes()).hexdigest()
        result = self._runner(self._compose("images", "--format", "json"))
        if result.returncode != 0:
            raise StackError(
                f"compose images failed (rc={result.returncode}):\n"
                f"{' '.join(result.args)}\n{result.stdout}\n{result.stderr}"
            )
        return digest, parse_image_digests(result.stdout)

    def _write_override(self, port: int | None) -> Path:
        """Write the generated compose override (port mapping + DATABASE_URL).

        ``ports: !override`` replaces (not merges) the release file's
        fixed host mapping — Docker Compose v2.24+ tag semantics. Written
        as literal YAML because ``!override`` is a compose-specific tag.
        """
        self._override_dir.mkdir(parents=True, exist_ok=True)
        path = self._override_dir / OVERRIDE_FILE_NAME
        database_url = _DB_URL_TEMPLATE.format(
            user=_DB_USER, password=_DB_PASSWORD, host=_DB_HOST, db=_DB_NAME
        )
        lines = [
            "services:",
            "  narrare:",
            "    environment:",
            f'      DATABASE_URL: "{database_url}"',
        ]
        if port is not None:
            lines += [
                "    ports: !override",
                f'      - "127.0.0.1:{port}:{_API_CONTAINER_PORT}"',
            ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _prefixed_resources(self) -> list[str]:
        """List docker resources whose name carries the project prefix."""
        found: list[str] = []
        listings: tuple[tuple[str, ...], ...] = (
            ("ps", "-a", "--format", "{{.Names}}"),
            ("volume", "ls", "--format", "{{.Name}}"),
            ("network", "ls", "--format", "{{.Name}}"),
        )
        for tail in listings:
            result = self._runner(["docker", *tail])
            if result.returncode != 0:
                raise StackError(
                    f"resource listing failed (rc={result.returncode}): "
                    f"{' '.join(result.args)}\n{result.stderr}"
                )
            found += [name for name in result.stdout.splitlines() if name.startswith(self._prefix)]
        return found

    def _compose(self, *args: str, override: Path | None = None) -> list[str]:
        argv = [
            "docker",
            "compose",
            "-p",
            self._prefix,
            "-f",
            str(RELEASE_COMPOSE_FILE),
        ]
        if override is not None:
            argv += ["-f", str(override)]
        return [*argv, *args]
