"""Fakes and factory for the hybrid-stack tests (``test_stack`` precedent).

NO docker, NO real subprocesses: compose I/O goes through the canned
``CommandRunner``, the uvicorn spawn/kill through fake spawner/terminator
seams, postgres waiting and port probing through recording fakes. Shared
by ``test_stack_hybrid.py`` (mode behaviour) — kept out of the test
modules per RULE-04/RULE-06 (test files at 400-line hard limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from benchmark.config import (
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    LlmConfig,
    RunConfig,
    StackConfig,
)
from benchmark.stack import CommandResult, StackManager

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from typing import IO

    from benchmark.stack_common import HealthWaiter
    from benchmark.stack_hybrid import ManagedProcess, PgWaiter

PREFIX: Final[str] = "narrare-benchmark"
API_PORT: Final[int] = 18123
PG_PORT: Final[int] = 18432
API_URL: Final[str] = f"http://127.0.0.1:{API_PORT}"
EXPECTED_DATABASE_URL: Final[str] = (
    f"postgresql+asyncpg://narrare:narrare@127.0.0.1:{PG_PORT}/narrare_dev"
)


class FakeRunner:
    """Canned ``CommandRunner``: matches argv tails to ``(rc, out, err)``.

    Compose ``down`` invocations are appended to the shared ``events``
    list so tests can assert kill-before-down ordering.
    """

    def __init__(
        self,
        responses: dict[tuple[str, ...], tuple[int, str, str]] | None = None,
        events: list[str] | None = None,
    ) -> None:
        self.responses: dict[tuple[str, ...], tuple[int, str, str]] = responses or {}
        self.calls: list[list[str]] = []
        self.events = events if events is not None else []

    def __call__(self, args: Sequence[str]) -> CommandResult:
        call = list(args)
        self.calls.append(call)
        if call[-3:] == ["down", "-v", "--remove-orphans"]:
            self.events.append("compose-down")
        for tail, (rc, out, err) in self.responses.items():
            if len(call) >= len(tail) and tuple(call[-len(tail) :]) == tail:
                return CommandResult(tuple(call), rc, out, err)
        return CommandResult(tuple(call), 0, "", "")


class FakeProcess:
    """Process-handle fake: scripted pid and exit code."""

    def __init__(self, pid: int, exit_code: int | None = None) -> None:
        self.pid = pid
        self.exit_code = exit_code

    def poll(self) -> int | None:
        return self.exit_code

    def wait(self, timeout: float | None = None) -> int:
        assert self.exit_code is not None, "wait() on a still-running fake"
        return self.exit_code


class FakeSpawner:
    """Records the spawn call; writes one line to the log handle (child output)."""

    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.calls: list[list[str]] = []
        self.cwds: list[Path] = []
        self.envs: list[dict[str, str]] = []
        self.log_handles: list[object] = []

    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        stdout: IO[bytes],
        stderr: IO[bytes],
    ) -> ManagedProcess:
        stdout.write(b"uvicorn-boom\n")
        self.calls.append(list(argv))
        self.cwds.append(cwd)
        self.envs.append(env)
        self.log_handles.append(stdout)
        return self.process


class FakeTerminator:
    """Records the kill call; simulates the process dying on SIGTERM."""

    def __init__(self, events: list[str]) -> None:
        self.calls: list[tuple[int, float]] = []
        self.events = events

    def __call__(self, process: ManagedProcess, /, *, grace_s: float) -> None:
        assert isinstance(process, FakeProcess)
        self.calls.append((process.pid, grace_s))
        process.exit_code = 0
        self.events.append("terminate-uvicorn")


class StubbornTerminator:
    """Records the kill call but the process SURVIVES (residue scenario)."""

    def __call__(self, process: ManagedProcess, /, *, grace_s: float) -> None:
        assert isinstance(process, FakeProcess)
        process.exit_code = None


class RecordingPgWait:
    """No-op postgres waiter recording ``(host, port)`` calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def __call__(self, host: str, port: int, /) -> None:
        self.calls.append((host, port))


class RecordingProber:
    """Port prober recording calls; ``result`` is publicly switchable."""

    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.calls: list[tuple[str, int]] = []

    def __call__(self, host: str, port: int, /) -> bool:
        self.calls.append((host, port))
        return self.result


class ScriptedProbe:
    """Health probe returning pre-scripted results, recording probe URLs."""

    def __init__(self, results: list[bool]) -> None:
        self._results = list(results)
        self.calls: list[str] = []

    def healthy(self, base_url: str) -> bool:
        self.calls.append(base_url)
        assert self._results, "ScriptedProbe exhausted — wait loop probed too often"
        return self._results.pop(0)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_config(mode: str = "hybrid") -> BenchmarkConfig:
    return BenchmarkConfig(
        stack=StackConfig(PREFIX, 18080, 18180, mode),
        api=ApiConfig(None, 60.0),
        auth=AuthConfig("benchmark@example.com", "change-me-benchmark-password"),
        llm=LlmConfig("anthropic", "sk-test-dummy", "m", "http://localhost:11434", "general"),
        run=RunConfig(["clean"], ["incremental"], False, []),
    )


def make_manager(
    tmp_path: Path,
    runner: FakeRunner,
    process: FakeProcess,
    *,
    spawner: FakeSpawner | None = None,
    terminator: FakeTerminator | StubbornTerminator | None = None,
    pg_waiter: PgWaiter | None = None,
    tcp_prober: RecordingProber | None = None,
    probe: ScriptedProbe | None = None,
    waiter: HealthWaiter | None = None,
) -> StackManager:
    """Manager with deterministic ports: postgres PG_PORT first, API API_PORT."""
    ports = [PG_PORT, API_PORT]
    return StackManager(
        make_config(),
        runner=runner,
        probe=probe or ScriptedProbe([True]),
        waiter=waiter,
        port_selector=lambda low, high: ports.pop(0),
        override_dir=tmp_path / "stack-override",
        spawner=spawner or FakeSpawner(process),
        terminator=terminator or FakeTerminator(runner.events),
        pg_waiter=pg_waiter or RecordingPgWait(),
        tcp_prober=tcp_prober or RecordingProber(),
        uvicorn_log_dir=tmp_path / "uvicorn-logs",
    )
