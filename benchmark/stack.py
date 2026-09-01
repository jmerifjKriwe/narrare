"""Benchmark stack orchestration facade — mode dispatch (PO ruling).

The stack is HYBRID by default (``stack.mode: hybrid``): only the
``postgres`` service runs in docker (from ``docker-compose.dev.yml``,
prefixed compose project) while the API runs as a LOCAL uvicorn
subprocess from the working tree — the benchmark measures current code
(see ``benchmark.stack_hybrid``). ``stack.mode: containers`` preserves
the image-based full-app stack via ``docker-compose.release.yml`` as the
non-default option (see ``benchmark.stack_containers``).

``StackManager`` is the stable seam consumed by the runner (Task 15) and
the CLI: ``up()`` / ``teardown()`` / ``is_up()`` / ``facts()`` delegate
to the mode implementation selected from the config — no mode logic
lives here (RULE-06). Shared seams (subprocess runner, health probe and
waiter, port selection, compose argv, residue verification) live in
``benchmark.stack_common``; this module re-exports them so
``from benchmark.stack import …`` stays the single public import surface
(``benchmark.config`` precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmark.stack_common import (
    DEV_COMPOSE_FILE,
    HEALTH_TIMEOUT_S,
    POLL_INTERVAL_S,
    RELEASE_COMPOSE_FILE,
    REPO_ROOT,
    CommandResult,
    CommandRunner,
    HealthProbe,
    HealthWaiter,
    HttpxHealthProbe,
    StackError,
    compose_argv,
    default_override_dir,
    postgres_url,
    prefixed_leftovers,
    run_subprocess,
    select_free_port,
)
from benchmark.stack_containers import (
    APP_IMAGE,
    OVERRIDE_FILE_NAME,
    ContainersStack,
    ImageSource,
    ensure_image,
    parse_image_digests,
)
from benchmark.stack_hybrid import (
    POSTGRES_OVERRIDE_FILE_NAME,
    HybridStack,
    ManagedProcess,
    PgWaiter,
    ProcessSpawner,
    ProcessTerminator,
    TcpProber,
    default_uvicorn_log_dir,
    spawn_process_group,
    tcp_accepts,
    terminate_process_group,
    wait_tcp,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from benchmark.config_schemas import BenchmarkConfig

__all__ = [
    "APP_IMAGE",
    "DEV_COMPOSE_FILE",
    "OVERRIDE_FILE_NAME",
    "POSTGRES_OVERRIDE_FILE_NAME",
    "RELEASE_COMPOSE_FILE",
    "REPO_ROOT",
    "CommandResult",
    "ContainersStack",
    "HealthProbe",
    "HealthWaiter",
    "HybridStack",
    "ImageSource",
    "ManagedProcess",
    "PgWaiter",
    "ProcessSpawner",
    "ProcessTerminator",
    "StackError",
    "StackManager",
    "TcpProber",
    "compose_argv",
    "ensure_image",
    "parse_image_digests",
    "postgres_url",
    "prefixed_leftovers",
    "run_subprocess",
    "select_free_port",
    "spawn_process_group",
    "tcp_accepts",
    "terminate_process_group",
    "wait_tcp",
]

_CONTAINERS_MODE = "containers"


class StackManager:
    """Bring up, health-check, and tear down the benchmark stack (any mode)."""

    def __init__(
        self,
        config: BenchmarkConfig,
        *,
        runner: CommandRunner | None = None,
        probe: HealthProbe | None = None,
        waiter: HealthWaiter | None = None,
        port_selector: Callable[[int, int], int] = select_free_port,
        override_dir: Path | None = None,
        spawner: ProcessSpawner = spawn_process_group,
        terminator: ProcessTerminator = terminate_process_group,
        pg_waiter: PgWaiter = wait_tcp,
        tcp_prober: TcpProber = tcp_accepts,
        uvicorn_log_dir: Path | None = None,
    ) -> None:
        self._prefix = config.stack.project_name
        runner_impl: CommandRunner = runner if runner is not None else run_subprocess
        if waiter is None:
            probe_impl = probe if probe is not None else HttpxHealthProbe()
            waiter = HealthWaiter(
                probe_impl.healthy,
                timeout_s=HEALTH_TIMEOUT_S,
                interval_s=POLL_INTERVAL_S,
            )
        override = override_dir if override_dir is not None else default_override_dir(self._prefix)
        log_dir = (
            uvicorn_log_dir
            if uvicorn_log_dir is not None
            else default_uvicorn_log_dir(self._prefix)
        )
        if config.stack.mode == _CONTAINERS_MODE:
            self._impl: ContainersStack | HybridStack = ContainersStack(
                config,
                runner=runner_impl,
                waiter=waiter,
                port_selector=port_selector,
                override_dir=override,
            )
        else:
            self._impl = HybridStack(
                config,
                runner=runner_impl,
                waiter=waiter,
                port_selector=port_selector,
                override_dir=override,
                spawner=spawner,
                terminator=terminator,
                pg_waiter=pg_waiter,
                tcp_prober=tcp_prober,
                uvicorn_log_dir=log_dir,
            )

    def up(self) -> str:
        """Start the stack; return the API base URL it became healthy on."""
        return self._impl.up()

    def teardown(self, *, verify: bool = True) -> None:
        """Remove the stack and verify residue-free (mode-specific)."""
        self._impl.teardown(verify=verify)

    def is_up(self) -> bool:
        """Whether the stack currently runs (mode-specific)."""
        return self._impl.is_up()

    def facts(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        """Stack identity facts for the run manifest (mode-specific)."""
        return self._impl.facts()
