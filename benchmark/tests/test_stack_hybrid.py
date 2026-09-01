"""Unit tests for the hybrid stack mode (PO ruling default).

Hybrid = dev-compose ``postgres`` container + the API as a LOCAL uvicorn
subprocess from the working tree. Verifies the up sequence (compose
postgres with port override → postgres TCP wait → uvicorn spawn with
argv/cwd/env incl. the dynamic-port ``DATABASE_URL`` and the pinned-off
``NARRARE_E2E_TEST`` → API health poll → E2E-test-mode log guard),
teardown ordering (uvicorn killed BEFORE compose down, both verified),
and mode-scoped ``is_up``/``facts`` — including that the containers-only
image acquisition never runs in hybrid mode. The TCP-poll and
process-group-termination seams are covered in
``test_stack_hybrid_seams.py``; shared fakes live in
``stack_hybrid_helpers.py`` (RULE-04 split).
"""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING

import pytest

from benchmark.stack import (
    DEV_COMPOSE_FILE,
    POSTGRES_OVERRIDE_FILE_NAME,
    REPO_ROOT,
    HealthWaiter,
    StackError,
)
from benchmark.tests.stack_hybrid_helpers import (
    API_PORT,
    API_URL,
    EXPECTED_DATABASE_URL,
    PG_PORT,
    PREFIX,
    FakeProcess,
    FakeRunner,
    FakeSpawner,
    FakeTerminator,
    RecordingPgWait,
    RecordingProber,
    ScriptedProbe,
    StubbornTerminator,
    make_manager,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestHybridUp:
    def test_compose_up_runs_only_postgres_with_port_override(self, tmp_path: Path) -> None:
        runner = FakeRunner()
        manager = make_manager(tmp_path, runner, FakeProcess(4242))
        manager.up()
        (up_call,) = [c for c in runner.calls if c[-3:] == ["up", "-d", "postgres"]]
        assert up_call == [
            "docker",
            "compose",
            "-p",
            PREFIX,
            "-f",
            str(DEV_COMPOSE_FILE),
            "-f",
            str(tmp_path / "stack-override" / POSTGRES_OVERRIDE_FILE_NAME),
            "up",
            "-d",
            "postgres",
        ]
        override = (tmp_path / "stack-override" / POSTGRES_OVERRIDE_FILE_NAME).read_text(
            encoding="utf-8"
        )
        assert "ports: !override" in override
        assert f'"127.0.0.1:{PG_PORT}:5432"' in override

    def test_sequence_pg_wait_then_spawn_then_health_poll(self, tmp_path: Path) -> None:
        spawner = FakeSpawner(FakeProcess(4242))
        pg_waiter = RecordingPgWait()
        probe = ScriptedProbe([True])
        manager = make_manager(
            tmp_path,
            FakeRunner(),
            FakeProcess(4242),
            spawner=spawner,
            pg_waiter=pg_waiter,
            probe=probe,
        )
        url = manager.up()
        assert url == API_URL
        # pg wait BEFORE spawn; API health poll AFTER spawn
        assert pg_waiter.calls == [("127.0.0.1", PG_PORT)]
        assert len(spawner.calls) == 1
        assert probe.calls == [API_URL]

    def test_spawns_uvicorn_with_expected_argv_cwd_and_env(self, tmp_path: Path) -> None:
        spawner = FakeSpawner(FakeProcess(4242))
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242), spawner=spawner)
        manager.up()
        assert spawner.calls == [
            [
                "uv",
                "run",
                "uvicorn",
                "narrare._app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(API_PORT),
            ]
        ]
        assert spawner.cwds == [REPO_ROOT / "apps" / "api"]
        (env,) = spawner.envs
        assert env["DATABASE_URL"] == EXPECTED_DATABASE_URL
        assert env["PATH"] == os.environ["PATH"]  # rest of the environment inherited

    def test_spawn_output_lands_in_run_scoped_log_file(self, tmp_path: Path) -> None:
        spawner = FakeSpawner(FakeProcess(4242))
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242), spawner=spawner)
        manager.up()
        log_file = tmp_path / "uvicorn-logs" / "uvicorn.log"
        assert log_file.read_bytes() == b"uvicorn-boom\n"

    def test_spawns_uvicorn_with_e2e_test_mode_pinned_false(self, tmp_path: Path) -> None:
        """Rehearsal finding #6: the spawn env pins the E2E flag off."""
        spawner = FakeSpawner(FakeProcess(4242))
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242), spawner=spawner)
        manager.up()
        (env,) = spawner.envs
        assert env["NARRARE_E2E_TEST"] == "false"

    def test_e2e_test_mode_marker_in_log_refuses_up(self, tmp_path: Path) -> None:
        """Rehearsal finding #6: TestModel startup in the log → refuse."""
        spawner = FakeSpawner(
            FakeProcess(4242),
            log_line=(
                b"INFO: e2e_test_mode_active: "
                b"ALL LLM providers returning TestModel - no real API calls.\n"
            ),
        )
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242), spawner=spawner)
        with pytest.raises(StackError, match="E2E test mode"):
            manager.up()

    def test_e2e_guard_passes_on_clean_log(self, tmp_path: Path) -> None:
        """Near-miss line (``inactive`` ≠ ``active``) must NOT trip the guard."""
        spawner = FakeSpawner(
            FakeProcess(4242),
            log_line=b"INFO: e2e_test_mode_inactive is not the marker\n",
        )
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242), spawner=spawner)
        assert manager.up() == API_URL

    def test_health_wait_failure_wins_over_the_e2e_guard(self, tmp_path: Path) -> None:
        """Ordering: the guard runs only AFTER the health-wait succeeded."""
        waiter = HealthWaiter(
            ScriptedProbe([False]).healthy,
            timeout_s=0.0,
            interval_s=1.0,
            sleep=lambda _s: None,
            clock=FakeClockAtDeadline(),
        )
        spawner = FakeSpawner(
            FakeProcess(4242),
            log_line=b"INFO: e2e_test_mode_active: TestModel active\n",
        )
        manager = make_manager(
            tmp_path, FakeRunner(), FakeProcess(4242), spawner=spawner, waiter=waiter
        )
        with pytest.raises(StackError, match="uvicorn log tail") as excinfo:
            manager.up()
        assert "E2E test mode" not in str(excinfo.value)

    def test_compose_up_failure_raises_with_captured_output(self, tmp_path: Path) -> None:
        runner = FakeRunner({("up", "-d", "postgres"): (1, "up-out", "up-err")})
        manager = make_manager(tmp_path, runner, FakeProcess(4242))
        with pytest.raises(StackError, match="up-err"):
            manager.up()

    def test_pg_wait_failure_prevents_spawn(self, tmp_path: Path) -> None:
        spawner = FakeSpawner(FakeProcess(4242))

        def broken_pg_wait(host: str, port: int, /) -> None:
            raise StackError("postgres not ready")

        manager = make_manager(
            tmp_path,
            FakeRunner(),
            FakeProcess(4242),
            pg_waiter=broken_pg_wait,
            spawner=spawner,
        )
        with pytest.raises(StackError, match="postgres not ready"):
            manager.up()
        assert spawner.calls == []

    def test_health_timeout_includes_uvicorn_log_tail(self, tmp_path: Path) -> None:
        clock = FakeClockAtDeadline()
        waiter = HealthWaiter(
            ScriptedProbe([False]).healthy,
            timeout_s=0.0,
            interval_s=1.0,
            sleep=lambda _s: None,
            clock=clock,
        )
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242), waiter=waiter)
        with pytest.raises(StackError, match="uvicorn-boom") as excinfo:
            manager.up()
        assert "uvicorn log tail" in str(excinfo.value)

    def test_never_touches_docker_images_in_hybrid_mode(self, tmp_path: Path) -> None:
        runner = FakeRunner()
        manager = make_manager(tmp_path, runner, FakeProcess(4242))
        manager.up()
        assert [c for c in runner.calls if c[:2] == ["docker", "image"]] == []
        assert [c for c in runner.calls if "build" in c] == []


class TestHybridTeardown:
    def test_kills_uvicorn_before_compose_down_and_verifies_both(self, tmp_path: Path) -> None:
        events: list[str] = []
        runner = FakeRunner(events=events)
        terminator = FakeTerminator(events)
        manager = make_manager(tmp_path, runner, FakeProcess(4242), terminator=terminator)
        manager.up()
        events.clear()
        manager.teardown()
        assert events == ["terminate-uvicorn", "compose-down"]
        (down_call,) = [c for c in runner.calls if c[-3:] == ["down", "-v", "--remove-orphans"]]
        assert down_call[:4] == ["docker", "compose", "-p", PREFIX]
        assert str(DEV_COMPOSE_FILE) in down_call
        (kill,) = terminator.calls
        assert kill == (4242, 10.0)
        # residue verification ran: the three prefixed-resource listings
        listing_calls = [c for c in runner.calls if c[-2] == "--format"]
        assert [c[-1] for c in listing_calls] == [
            "{{.Names}}",
            "{{.Name}}",
            "{{.Name}}",
        ]

    def test_raises_when_uvicorn_survives(self, tmp_path: Path) -> None:
        prober = RecordingProber(result=True)
        manager = make_manager(
            tmp_path,
            FakeRunner(),
            FakeProcess(4242),
            terminator=StubbornTerminator(),
            tcp_prober=prober,
        )
        manager.up()
        with pytest.raises(StackError, match="uvicorn subprocess running"):
            manager.teardown()

    def test_exited_process_passes_even_if_probe_sees_traffic(self, tmp_path: Path) -> None:
        prober = RecordingProber(result=True)
        process = FakeProcess(4242)
        manager = make_manager(tmp_path, FakeRunner(), process, tcp_prober=prober)
        manager.up()
        process.exit_code = 0  # process exited → dead regardless of the probe
        manager.teardown()  # must not raise

    def test_tolerates_teardown_without_up(self, tmp_path: Path) -> None:
        events: list[str] = []
        runner = FakeRunner(events=events)
        terminator = FakeTerminator(events)
        manager = make_manager(tmp_path, runner, FakeProcess(4242), terminator=terminator)
        manager.teardown()
        assert terminator.calls == []
        assert [c for c in runner.calls if c[-3:] == ["down", "-v", "--remove-orphans"]]


class TestHybridIsUpFacts:
    def test_is_up_requires_live_process_and_open_port(self, tmp_path: Path) -> None:
        prober = RecordingProber(result=True)
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242), tcp_prober=prober)
        assert manager.is_up() is False  # never brought up
        manager.up()
        assert manager.is_up() is True
        prober.result = False
        assert manager.is_up() is False

    def test_facts_record_mode_pid_port_and_dev_compose_hash(self, tmp_path: Path) -> None:
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242))
        manager.up()
        digest, pairs = manager.facts()
        assert digest == hashlib.sha256(DEV_COMPOSE_FILE.read_bytes()).hexdigest()
        assert pairs == (
            ("api_port", str(API_PORT)),
            ("mode", "hybrid"),
            ("uvicorn_pid", "4242"),
        )

    def test_facts_before_up_raise(self, tmp_path: Path) -> None:
        manager = make_manager(tmp_path, FakeRunner(), FakeProcess(4242))
        with pytest.raises(StackError, match="before up"):
            manager.facts()


class FakeClockAtDeadline:
    """Clock that has already run past any deadline (deadline = now + 0)."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now
