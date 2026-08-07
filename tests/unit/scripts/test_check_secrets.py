"""Tests for scripts/check_secrets.py — Gitleaks wrapper behavior."""

from __future__ import annotations

import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.check_secrets as check_secrets  # noqa: E402


def _noop_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the machine-wide flock with a no-op pass-through."""

    @contextmanager
    def _ctx() -> Iterator[None]:
        yield

    monkeypatch.setattr(check_secrets, "_machine_lock", _ctx)


def test_main_when_gitleaks_missing_reports_actionable_install_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing local binary must fail with local install guidance."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text("title = 'test'\n", encoding="utf-8")
    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: None)

    exit_code = check_secrets.main(["--source", str(tmp_path), "--config", str(config)])

    captured = capsys.readouterr()
    assert exit_code == 127  # POSIX "command not found" (gitleaks missing)
    assert "Gitleaks binary not found" in captured.err
    assert "Install Gitleaks" in captured.err
    assert "just check-secrets" in captured.err


def test_full_mode_invokes_gitleaks_with_required_secret_scan_flags(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Full mode must invoke the mandatory CI/local Gitleaks gate flags."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text("title = 'test'\n", encoding="utf-8")
    _noop_lock(monkeypatch)
    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: "/usr/local/bin/gitleaks")

    calls: list[tuple[list[str], Path, float]] = []

    def fake_run(command: list[str], cwd: Path, timeout: float) -> int:
        calls.append((command, cwd, timeout))
        return 0

    monkeypatch.setattr(check_secrets, "_run_command_with_timeout", fake_run)

    exit_code = check_secrets.main(
        ["--source", str(tmp_path), "--config", str(config), "--timeout", "42"]
    )

    assert exit_code == 0
    assert calls == [
        (
            [
                "/usr/local/bin/gitleaks",
                "detect",
                "--source",
                str(tmp_path),
                "--redact",
                "--config",
                str(config),
            ],
            tmp_path,
            42.0,
        )
    ]


def test_default_config_resolves_to_project_root_gitleaks_toml() -> None:
    """Default config path must point at the tracked project .gitleaks.toml."""
    expected = _ROOT / ".gitleaks.toml"
    assert expected == check_secrets.DEFAULT_CONFIG
    assert check_secrets.DEFAULT_CONFIG.is_file(), (
        f"Expected tracked config at {expected}, but file is missing."
    )


def test_main_returns_wrapper_error_when_config_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing config file must fail with a configuration error (exit 2)."""
    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: "/usr/local/bin/gitleaks")
    missing_config = tmp_path / "does_not_exist.toml"

    exit_code = check_secrets.main(["--source", str(tmp_path), "--config", str(missing_config)])

    captured = capsys.readouterr()
    assert exit_code == check_secrets.EXIT_WRAPPER_ERROR
    assert "Gitleaks config not found" in captured.err


def test_main_returns_wrapper_error_when_source_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Full mode must fail with exit 2 when the source path does not exist."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text("title = 'test'\n", encoding="utf-8")
    _noop_lock(monkeypatch)
    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: "/usr/local/bin/gitleaks")
    missing_source = tmp_path / "no_such_dir"

    exit_code = check_secrets.main(["--source", str(missing_source), "--config", str(config)])

    captured = capsys.readouterr()
    assert exit_code == check_secrets.EXIT_WRAPPER_ERROR
    assert "Secret scan source does not exist" in captured.err


# ── Staged mode (P1) ──────────────────────────────────────────────────────


def test_staged_mode_builds_no_git_command_against_staging_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Staged mode must scan a materialized staging dir with --no-git (no history)."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text("title = 'test'\n", encoding="utf-8")
    _noop_lock(monkeypatch)
    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: "/usr/local/bin/gitleaks")
    monkeypatch.setattr(
        check_secrets, "_staged_relative_paths", lambda: ["app/main.py", "lib/util.py"]
    )
    monkeypatch.setattr(check_secrets, "_materialize_staged_into", lambda _paths, _dest: 2)

    recorded: list[tuple[list[str], Path, float]] = []

    def fake_run(command: list[str], cwd: Path, timeout: float) -> int:
        recorded.append((command, cwd, timeout))
        return 0

    monkeypatch.setattr(check_secrets, "_run_command_with_timeout", fake_run)

    exit_code = check_secrets.main(["--staged", "--config", str(config), "--timeout", "90"])

    assert exit_code == 0
    assert len(recorded) == 1
    command, cwd, timeout = recorded[0]
    assert timeout == 90.0
    staging_dir = Path(command[4])
    assert command == [
        "/usr/local/bin/gitleaks",
        "detect",
        "--no-git",
        "--source",
        str(staging_dir),
        "--redact",
        "--config",
        str(config),
    ]
    # The staging dir is the cwd gitleaks runs from, and it lives under tmp.
    assert cwd == staging_dir
    assert staging_dir.is_absolute()


def test_staged_mode_with_no_staged_files_exits_zero_without_scanning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Nothing staged -> fast exit 0 without invoking Gitleaks at all."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text("title = 'test'\n", encoding="utf-8")
    _noop_lock(monkeypatch)
    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: "/usr/local/bin/gitleaks")
    monkeypatch.setattr(check_secrets, "_staged_relative_paths", lambda: [])

    def boom(_command: list[str], _cwd: Path, _timeout: float) -> int:
        raise AssertionError("Gitleaks must not run when nothing is staged")

    monkeypatch.setattr(check_secrets, "_run_command_with_timeout", boom)

    exit_code = check_secrets.main(["--staged", "--config", str(config)])

    assert exit_code == 0


def test_materialize_staged_into_skips_binary_and_missing_blobs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Binary blobs (NUL bytes) and missing blobs are skipped; text files written."""
    paths = ["text.txt", "binary.bin", "gone.txt"]
    blobs = {
        "text.txt": b"hello world",
        "binary.bin": b"\x00\x01\x02binary",
    }
    monkeypatch.setattr(
        check_secrets,
        "_staged_blob",
        lambda rel: blobs.get(rel),
    )

    count = check_secrets._materialize_staged_into(paths, tmp_path)

    assert count == 1
    assert (tmp_path / "text.txt").read_bytes() == b"hello world"
    assert not (tmp_path / "binary.bin").exists()
    assert not (tmp_path / "gone.txt").exists()


# ── Hard timeout + process-group kill (P2) ─────────────────────────────────


def test_timeout_kills_process_group_and_returns_124(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """On timeout the whole process group is SIGKILLed and exit 124 is returned."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text("title = 'test'\n", encoding="utf-8")
    _noop_lock(monkeypatch)
    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: "/usr/local/bin/gitleaks")

    class _FakePopen:
        pid = 4242

        def __init__(self, command: list[str], **_kwargs: object) -> None:
            self.command = command

        def communicate(self, timeout: float | None = None) -> tuple[None, None]:
            raise subprocess.TimeoutExpired(self.command, timeout or 0.0)

    killed: list[int] = []
    monkeypatch.setattr(check_secrets.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(check_secrets, "_kill_process_group", killed.append)

    exit_code = check_secrets.main(
        ["--source", str(tmp_path), "--config", str(config), "--timeout", "1"]
    )

    assert exit_code == 124  # GNU `timeout` convention (wrapper killed gitleaks)
    assert killed == [4242]


def test_run_command_with_timeout_returns_gitleaks_returncode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A normal (non-timed-out) run returns Gitleaks' own return code."""

    class _FakePopen:
        returncode = 1  # Gitleaks "found secrets" code

        def __init__(self, command: list[str], **_kwargs: object) -> None:
            self.command = command

        def communicate(self, timeout: float | None = None) -> tuple[None, None]:
            return (None, None)

    monkeypatch.setattr(check_secrets.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(check_secrets, "_kill_process_group", lambda _pid: None)

    exit_code = check_secrets._run_command_with_timeout(
        ["gitleaks", "detect"], tmp_path, timeout=30.0
    )

    assert exit_code == check_secrets.EXIT_GITLEAKS_FINDING


# ── Concurrency guard (P3) ──────────────────────────────────────────────────


def test_lock_busy_returns_distinct_exit_with_retry_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A held concurrency lock must fail fast with exit 3 and a retry message."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text("title = 'test'\n", encoding="utf-8")
    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: "/usr/local/bin/gitleaks")
    monkeypatch.setattr(check_secrets, "LOCK_FILE", tmp_path / "test.lock")

    def _busy(_fd: int, _op: int) -> None:
        raise BlockingIOError("locked")

    monkeypatch.setattr(check_secrets.fcntl, "flock", _busy)

    exit_code = check_secrets.main(["--source", str(tmp_path), "--config", str(config)])

    captured = capsys.readouterr()
    assert exit_code == check_secrets.EXIT_LOCK_BUSY
    assert "retry" in captured.err.lower()
