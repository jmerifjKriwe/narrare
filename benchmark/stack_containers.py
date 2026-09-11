"""Containers stack mode — full app stack via the release compose file.

The non-default option (PO ruling; default is ``stack_hybrid``): the
repo's ``docker-compose.release.yml`` is the only compose file defining
the full application; the app image exposes the FastAPI API on container
port 8000.

Image acquisition: no release image exists on GHCR yet, so with
``stack.build_image: auto`` (containers-mode-only setting)
``ContainersStack.up()`` first inspects the app image locally and, when
missing, builds it from the repo ``Dockerfile`` — instead of letting
compose fail on the pull. ``stack.build_image: never`` preserves
pull-only behavior for when release images exist.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import TYPE_CHECKING, Final, cast

from benchmark.stack_common import (
    LOG_TAIL_LINES,
    RELEASE_COMPOSE_FILE,
    REPO_ROOT,
    StackError,
    compose_argv,
    postgres_url,
    prefixed_leftovers,
    run_subprocess,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from benchmark.config_schemas import BenchmarkConfig
    from benchmark.stack_common import CommandRunner, HealthWaiter

OVERRIDE_FILE_NAME: Final[str] = "benchmark-compose-override.yml"
# The release compose file's app-image default (its
# ``${NARRARE_IMAGE:-ghcr.io/jmerifjkriwe/narrare}:${NARRARE_VERSION:-latest}``
# with the env overrides unset — the runner never sets them). Must mirror
# that line when the default changes.
APP_IMAGE: Final[str] = "ghcr.io/jmerifjkriwe/narrare:latest"

_API_CONTAINER_PORT: Final[int] = 8000
_DB_CONTAINER_PORT: Final[int] = 5432
_DB_HOST: Final[str] = "postgres"  # compose service hostname
_DB_NAME: Final[str] = "narrare"


class ImageSource(Enum):
    """Where the app image came from — the ``ensure_image`` result."""

    LOCAL_PRESENT = "local-present"
    BUILT = "built"


def ensure_image(image: str, *, runner: CommandRunner = run_subprocess) -> ImageSource:
    """Guarantee the app image exists locally before ``compose up``.

    ``docker image inspect`` decides; on miss the image is built from the
    repo ``Dockerfile`` (context: repo root). Build failure raises
    ``StackError`` with the captured output — never a bare pull attempt,
    which would fail against the not-yet-existing GHCR release image.
    """
    inspect = runner(["docker", "image", "inspect", image])
    if inspect.returncode == 0:
        return ImageSource.LOCAL_PRESENT
    build = runner(
        ["docker", "build", "-t", image, "-f", str(REPO_ROOT / "Dockerfile"), str(REPO_ROOT)]
    )
    if build.returncode != 0:
        raise StackError(
            f"docker build failed for {image} (rc={build.returncode}):\n"
            f"{' '.join(build.args)}\n{build.stdout}\n{build.stderr}"
        )
    return ImageSource.BUILT


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


class ContainersStack:
    """Bring up, health-check, and tear down the image-based compose stack."""

    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        runner: CommandRunner,
        waiter: HealthWaiter,
        port_selector: Callable[[int, int], int],
        override_dir: Path,
    ) -> None:
        self._config = config
        self._prefix = config.stack.project_name
        self._runner = runner
        self._waiter = waiter
        self._port_selector = port_selector
        self._override_dir = override_dir

    def up(self) -> str:
        """Start the stack; return the API base URL it became healthy on."""
        if self._config.stack.build_image == "auto":
            ensure_image(APP_IMAGE, runner=self._runner)
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
                self._compose("logs", "--no-color", "--tail", LOG_TAIL_LINES, override=override)
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
            leftovers = prefixed_leftovers(self._prefix, runner=self._runner)
            if leftovers:
                raise StackError(
                    f"teardown left resources behind (prefix {self._prefix!r}): {leftovers}"
                )

    def is_up(self) -> bool:
        """Whether any service of the project currently runs."""
        result = self._runner(self._compose("ps", "--status", "running", "--format", "{{.Name}}"))
        return result.returncode == 0 and bool(result.stdout.strip())

    def facts(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        """Stack identity facts: release-compose SHA-256 + image digests."""
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
        database_url = postgres_url(_DB_HOST, _DB_CONTAINER_PORT, _DB_NAME)
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

    def _compose(self, *args: str, override: Path | None = None) -> list[str]:
        return compose_argv(self._prefix, RELEASE_COMPOSE_FILE, *args, override=override)
