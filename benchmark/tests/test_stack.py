"""Unit tests for ``benchmark.stack`` — compose commands, wait loop, teardown.

NO docker required: subprocess I/O goes through a fake ``CommandRunner``,
health polling through scripted probes with an injected clock, and the
port selector is stubbed. Command construction, prefix filtering, and
failure output are asserted literally.
"""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import pytest

from benchmark.config import (
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    LlmConfig,
    RunConfig,
    StackConfig,
)
from benchmark.stack import (
    OVERRIDE_FILE_NAME,
    RELEASE_COMPOSE_FILE,
    CommandResult,
    HealthWaiter,
    StackError,
    StackManager,
    run_subprocess,
    select_free_port,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

PREFIX = "narrare-benchmark"
API_URL = "http://127.0.0.1:18123"


class FakeRunner:
    """Canned ``CommandRunner``: matches argv tails to ``(rc, out, err)``."""

    def __init__(
        self, responses: dict[tuple[str, ...], tuple[int, str, str]] | None = None
    ) -> None:
        self.responses: dict[tuple[str, ...], tuple[int, str, str]] = responses or {}
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> CommandResult:
        call = list(args)
        self.calls.append(call)
        for tail, (rc, out, err) in self.responses.items():
            if len(call) >= len(tail) and tuple(call[-len(tail) :]) == tail:
                return CommandResult(tuple(call), rc, out, err)
        return CommandResult(tuple(call), 0, "", "")


class ScriptedProbe:
    """Health probe returning pre-scripted results, recording probe URLs."""

    def __init__(self, results: list[bool]) -> None:
        self._results = list(results)
        self.calls: list[str] = []

    def healthy(self, base_url: str) -> bool:
        self.calls.append(base_url)
        if not self._results:
            pytest.fail("ScriptedProbe exhausted — wait loop probed too often")
        return self._results.pop(0)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_config(base_url: str | None = None) -> BenchmarkConfig:
    return BenchmarkConfig(
        # mode="containers": this file tests the image-based stack path,
        # which is the NON-default option since the PO ruling (default:
        # hybrid, tested in test_stack_hybrid.py).
        stack=StackConfig(PREFIX, 18080, 18180, "containers"),
        api=ApiConfig(base_url, 60.0),
        auth=AuthConfig("benchmark@example.com", "change-me-benchmark-password"),
        llm=LlmConfig("anthropic", "sk-test-dummy", "m", "http://localhost:11434", "general"),
        run=RunConfig(["clean"], ["incremental"], False, []),
    )


def make_manager(
    runner: FakeRunner,
    probe: ScriptedProbe,
    override_dir: Path,
    *,
    base_url: str | None = None,
    waiter: HealthWaiter | None = None,
) -> StackManager:
    return StackManager(
        make_config(base_url),
        runner=runner,
        probe=probe,
        waiter=waiter,
        port_selector=lambda low, high: 18123,
        override_dir=override_dir,
    )


@pytest.fixture()
def override_dir(tmp_path: Path) -> Path:
    return tmp_path / "stack-override"


@pytest.fixture()
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture()
def probe() -> ScriptedProbe:
    return ScriptedProbe([True])


class TestUp:
    def test_builds_expected_compose_up_command(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        make_manager(runner, probe, override_dir).up()
        (up_call,) = [c for c in runner.calls if c[-2:] == ["up", "-d"]]
        assert up_call == [
            "docker",
            "compose",
            "-p",
            PREFIX,
            "-f",
            str(RELEASE_COMPOSE_FILE),
            "-f",
            str(override_dir / OVERRIDE_FILE_NAME),
            "up",
            "-d",
        ]

    def test_writes_port_override_for_selected_port(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        make_manager(runner, probe, override_dir).up()
        content = (override_dir / OVERRIDE_FILE_NAME).read_text(encoding="utf-8")
        assert "ports: !override" in content
        assert '"127.0.0.1:18123:8000"' in content
        assert "DATABASE_URL:" in content

    def test_derives_base_url_from_selected_port_and_probes_it(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        url = make_manager(runner, probe, override_dir).up()
        assert url == API_URL
        assert probe.calls == [API_URL]

    def test_base_url_override_skips_port_injection(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        url = make_manager(runner, probe, override_dir, base_url="http://localhost:9999").up()
        assert url == "http://localhost:9999"
        content = (override_dir / OVERRIDE_FILE_NAME).read_text(encoding="utf-8")
        assert "ports:" not in content
        assert probe.calls == ["http://localhost:9999"]

    def test_compose_failure_raises_with_captured_output(
        self, override_dir: Path, probe: ScriptedProbe
    ) -> None:
        runner = FakeRunner({("up", "-d"): (1, "up-stdout", "up-stderr")})
        with pytest.raises(StackError, match="up-stderr"):
            make_manager(runner, probe, override_dir).up()

    def test_health_timeout_includes_compose_logs(
        self, runner: FakeRunner, override_dir: Path
    ) -> None:
        runner.responses[("logs", "--no-color", "--tail", "200")] = (
            0,
            "compose-log-line",
            "",
        )
        probe = ScriptedProbe([False])
        deadline_clock = FakeClock()
        deadline_clock.now = 100.0  # any probe fails the 0s deadline check
        waiter = HealthWaiter(
            probe.healthy,
            timeout_s=0.0,
            interval_s=1.0,
            sleep=lambda _s: None,
            clock=deadline_clock,
        )
        with pytest.raises(StackError, match="compose-log-line") as excinfo:
            make_manager(runner, probe, override_dir, waiter=waiter).up()
        assert "did not become healthy" in str(excinfo.value)
        (logs_call,) = [c for c in runner.calls if c[-1] == "200"]
        assert logs_call[-4:] == ["logs", "--no-color", "--tail", "200"]


class TestTeardown:
    def test_runs_down_with_volumes_and_orphans(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        make_manager(runner, probe, override_dir).teardown()
        (down_call,) = [c for c in runner.calls if c[-3:] == ["down", "-v", "--remove-orphans"]]
        assert down_call[:2] == ["docker", "compose"]
        assert PREFIX in down_call
        assert str(RELEASE_COMPOSE_FILE) in down_call

    def test_verification_lists_all_three_resource_kinds(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        make_manager(runner, probe, override_dir).teardown()
        listing_calls = [c for c in runner.calls if c[-2] == "--format"]
        assert [c[-1] for c in listing_calls] == [
            "{{.Names}}",  # containers
            "{{.Name}}",  # volumes
            "{{.Name}}",  # networks
        ]
        assert listing_calls[0][:2] == ["docker", "ps"]
        assert listing_calls[1][:2] == ["docker", "volume"]
        assert listing_calls[2][:2] == ["docker", "network"]

    def test_verification_flags_prefixed_leftovers(
        self, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        runner = FakeRunner(
            {
                ("ps", "-a", "--format", "{{.Names}}"): (
                    0,
                    f"other-project-db-1\n{PREFIX}-narrare-1\n",
                    "",
                ),
                ("volume", "ls", "--format", "{{.Name}}"): (0, "", ""),
                ("network", "ls", "--format", "{{.Name}}"): (0, "", ""),
            }
        )
        with pytest.raises(StackError, match=f"{PREFIX}-narrare-1"):
            make_manager(runner, probe, override_dir).teardown()

    def test_verification_flags_prefixed_volumes(
        self, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        runner = FakeRunner(
            {
                ("ps", "-a", "--format", "{{.Names}}"): (0, "", ""),
                ("volume", "ls", "--format", "{{.Name}}"): (
                    0,
                    f"{PREFIX}_postgres_data\n",
                    "",
                ),
                ("network", "ls", "--format", "{{.Name}}"): (0, "", ""),
            }
        )
        with pytest.raises(StackError, match=f"{PREFIX}_postgres_data"):
            make_manager(runner, probe, override_dir).teardown()

    def test_verification_ignores_non_prefixed_resources(
        self, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        runner = FakeRunner(
            {
                ("ps", "-a", "--format", "{{.Names}}"): (0, "unrelated-thing\n", ""),
                ("volume", "ls", "--format", "{{.Name}}"): (0, "somevolume\n", ""),
                ("network", "ls", "--format", "{{.Name}}"): (0, "bridge\n", ""),
            }
        )
        make_manager(runner, probe, override_dir).teardown()  # must not raise

    def test_verification_disabled_skips_listing(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        make_manager(runner, probe, override_dir).teardown(verify=False)
        assert not [c for c in runner.calls if "--format" in c]

    def test_listing_failure_raises(self, probe: ScriptedProbe, override_dir: Path) -> None:
        runner = FakeRunner({("ps", "-a", "--format", "{{.Names}}"): (1, "", "ps-err")})
        with pytest.raises(StackError, match="ps-err"):
            make_manager(runner, probe, override_dir).teardown()


class TestIsUp:
    def test_true_when_services_running(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        runner.responses[("ps", "--status", "running", "--format", "{{.Name}}")] = (
            0,
            f"{PREFIX}-narrare-1\n",
            "",
        )
        assert make_manager(runner, probe, override_dir).is_up() is True

    def test_false_when_nothing_running(
        self, runner: FakeRunner, probe: ScriptedProbe, override_dir: Path
    ) -> None:
        assert make_manager(runner, probe, override_dir).is_up() is False


class TestHealthWaiter:
    def test_polls_until_probe_reports_healthy(self) -> None:
        probe = ScriptedProbe([False, False, True])
        clock = FakeClock()
        HealthWaiter(
            probe.healthy,
            timeout_s=10.0,
            interval_s=2.0,
            sleep=clock.advance,
            clock=clock,
        ).wait(API_URL)
        assert probe.calls == [API_URL, API_URL, API_URL]
        assert clock.now == 4.0  # one sleep between consecutive probes

    def test_raises_at_deadline(self) -> None:
        probe = ScriptedProbe([False] * 10)
        clock = FakeClock()
        with pytest.raises(StackError, match="did not become healthy"):
            HealthWaiter(
                probe.healthy,
                timeout_s=6.0,
                interval_s=2.0,
                sleep=clock.advance,
                clock=clock,
            ).wait(API_URL)
        assert clock.now == 6.0  # raised exactly at the deadline


class TestPortSelection:
    def test_skips_occupied_ports(self) -> None:
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            held.listen(1)
            occupied = held.getsockname()[1]
            assert select_free_port(occupied, occupied + 5) != occupied

    def test_raises_when_range_exhausted(self) -> None:
        with socket.socket() as held:
            held.bind(("127.0.0.1", 0))
            held.listen(1)
            occupied = held.getsockname()[1]
            with pytest.raises(StackError, match="no free port"):
                select_free_port(occupied, occupied)


class TestSubprocessRunner:
    def test_captures_stdout(self) -> None:
        import sys

        result = run_subprocess([sys.executable, "-c", "print('runner-ok')"])
        assert result.returncode == 0
        assert "runner-ok" in result.stdout

    def test_captures_failure(self) -> None:
        import sys

        result = run_subprocess([sys.executable, "-c", "raise SystemExit(3)"])
        assert result.returncode == 3
