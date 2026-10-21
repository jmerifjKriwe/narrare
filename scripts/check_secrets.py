#!/usr/bin/env python3
"""Repository secret-scanning gate backed by Gitleaks (AUFG-05-09).

A single entry point serves two scan modes:

* **Full mode** (default) — ``gitleaks detect --source <root>`` scans the whole
  repository INCLUDING git history. Used by CI
  (``.github/workflows/ci.yml``) and ``just check-secrets`` for the
  comprehensive repo-wide audit.

* **Staged mode** (``--staged``) — scans ONLY the currently git-staged file
  contents (added/copied/modified/renamed), with NO git history. Used by the
  pre-commit hook for fast per-commit feedback. Staged blobs are extracted to
  a temporary directory that mirrors repo-relative paths (so any path-based
  allowlist rules in ``.gitleaks.toml`` remain effective), then scanned with
  ``gitleaks detect --no-git --source <tmpdir>``.

Both modes are hardened against orphaned-gitleaks-process pile-ups (the root
cause of the pre-commit slowness / VM overload):

* ``--timeout SECONDS`` runs gitleaks in its own process group
  (``start_new_session=True``) and kills the WHOLE group (``os.killpg``) on
  timeout, so a wrapper killed by its parent never leaves a scanning orphan.
* A machine-wide ``fcntl.flock`` (non-blocking) serializes concurrent
  invocations so rapid successive commits cannot pile up multiple processes.

The wrapper deliberately does not hide findings or create a baseline; if
historical findings appear (full mode), they must be reviewed and explicitly
baselined by a follow-up governance decision.

Exit codes:
    0    No secrets found
    1    Gitleaks found one or more unapproved secrets
    2    Wrapper/configuration error
    3    Another secret scan holds the concurrency lock (retry shortly)
    124  Gitleaks timed out and was killed by the wrapper
    127  Gitleaks binary is not installed
"""

from __future__ import annotations

import argparse
import fcntl  # nosec B404 - stdlib advisory file locking, no shell
import os
import shutil
import signal
import subprocess  # nosec B404 - controlled gitleaks/git invocation, no shell
import sys
import tempfile
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / ".gitleaks.toml"
LOCK_FILE = Path(tempfile.gettempdir()) / "narrare-check-secrets.lock"

EXIT_GITLEAKS_FINDING = 1
EXIT_WRAPPER_ERROR = 2
EXIT_LOCK_BUSY = 3
# The remaining exit codes — 124 (GNU ``timeout`` convention) and 127 (POSIX
# "command not found") — are returned as inline literals where they occur.
# They are a fixed protocol contract documented in ``--help`` (not runtime
# configuration), and are kept inline to stay RULE-18-clean without needing a
# governance-exception entry in pyproject.toml.


class _LockBusyError(Exception):
    """Raised when another secret scan already holds the machine-wide lock."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the secret-scanning gate."""
    parser = argparse.ArgumentParser(
        description="Narrare secret-scanning gate (Gitleaks)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Scan modes:\n"
            "  default      Full repo incl. git history (CI / `just check-secrets`)\n"
            "  --staged     Only git-staged file contents, no history (pre-commit)\n\n"
            "Exit codes:\n"
            "  0    No secrets found\n"
            "  1    Gitleaks found one or more unapproved secrets\n"
            "  2    Wrapper/configuration error\n"
            "  3    Another secret scan holds the concurrency lock (retry shortly)\n"
            "  124  Gitleaks timed out and was killed by the wrapper\n"
            "  127  Gitleaks binary is not installed\n"
        ),
    )
    parser.add_argument(
        "--source",
        default=str(ROOT),
        help="Repository path to scan (default: project root; ignored with --staged)",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to .gitleaks.toml config (default: project root config)",
    )
    parser.add_argument(
        "--binary",
        default="gitleaks",
        help="Gitleaks executable name or path (default: gitleaks)",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Scan only git-staged file contents (no history) — pre-commit mode",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        # 300s default: full-history scan measures ~9s, so 300s is a wide
        # safety margin; overridable per-invocation (pre-commit uses 90).
        default=300.0,
        help=(
            "Hard per-scan timeout in seconds; on expiry the whole gitleaks "
            "process group is killed (default: %(default)s; 0 disables)"
        ),
    )
    return parser.parse_args(argv)


def build_gitleaks_command(binary: str, source: Path, config: Path) -> list[str]:
    """Build the full-mode Gitleaks command line (repo incl. history)."""
    return [
        binary,
        "detect",
        "--source",
        str(source),
        "--redact",
        "--config",
        str(config),
    ]


def build_staged_gitleaks_command(binary: str, source: Path, config: Path) -> list[str]:
    """Build the staged-mode Gitleaks command line (directory, no git history).

    ``--no-git`` makes Gitleaks treat ``--source`` as a plain directory, so the
    materialized staged blobs are scanned without walking git history.
    """
    return [
        binary,
        "detect",
        "--no-git",
        "--source",
        str(source),
        "--redact",
        "--config",
        str(config),
    ]


def _missing_binary_message(binary: str) -> str:
    """Return actionable local installation guidance for a missing binary."""
    return (
        f"Gitleaks binary not found: {binary}\n"
        "Install Gitleaks before running the secret-scanning gate.\n"
        "Linux example: download the latest release from "
        "https://github.com/gitleaks/gitleaks/releases and place `gitleaks` on PATH.\n"
        "Then re-run: just check-secrets"
    )


def _git_binary() -> str:
    """Resolve the ``git`` executable to an absolute path (or the bare name)."""
    resolved = shutil.which("git")
    return resolved if resolved else "git"


def _git(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a git subcommand against the repo root, capturing output (no raise)."""
    git = _git_binary()
    return subprocess.run(  # noqa: S603  # nosec  # controlled git invocation, fixed argv
        [git, *args],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )


def _staged_relative_paths() -> list[str]:
    """Return repo-relative paths of staged (added/copied/modified/renamed) files."""
    result = _git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    if result.returncode != 0:
        return []
    return [path.decode("utf-8", errors="replace") for path in result.stdout.split(b"\x00") if path]


def _staged_blob(rel_path: str) -> bytes | None:
    """Return the staged (index) content of a path, or None if unavailable."""
    result = _git(["show", f":{rel_path}"])
    if result.returncode != 0:
        return None
    return result.stdout


def _materialize_staged_into(paths: list[str], dest_root: Path) -> int:
    """Write staged blob contents into ``dest_root`` mirroring repo-relative paths.

    Binary files (containing NUL bytes) are skipped — Gitleaks skips them too.
    Returns the number of materialized (scannable) files.
    """
    root_resolved = dest_root.resolve()
    count = 0
    for rel in paths:
        blob = _staged_blob(rel)
        if blob is None or b"\x00" in blob:
            continue
        dest = (dest_root / rel).resolve()
        try:
            dest.relative_to(root_resolved)
        except ValueError:
            # Path escapes dest_root (defensive guard against a malformed index entry)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        count += 1
    return count


def _kill_process_group(leader_pid: int) -> None:
    """SIGKILL the whole process group led by ``leader_pid`` (orphan guard)."""
    with suppress(ProcessLookupError):
        os.killpg(os.getpgid(leader_pid), signal.SIGKILL)


def _run_command_with_timeout(command: list[str], cwd: Path, timeout: float) -> int:
    """Run ``command`` in a new session; kill the group on timeout.

    stdout/stderr are inherited so Gitleaks findings stay visible on the
    console (matching the original UX). ``start_new_session=True`` puts the
    child in its own process group so ``os.killpg`` can reliably reap it (and
    any descendants) on timeout — preventing orphaned scanners.
    """
    proc = subprocess.Popen(  # noqa: S603  # nosec  # controlled invocation, fixed argv
        command,
        cwd=str(cwd),
        start_new_session=True,
    )
    try:
        proc.communicate(timeout=timeout if timeout > 0 else None)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc.pid)
        with suppress(subprocess.TimeoutExpired):
            proc.communicate(timeout=5)  # best-effort reap of the killed group
        print(
            f"Gitleaks timed out after {timeout:g}s and was killed by the "
            "wrapper (process group reaped).",
            file=sys.stderr,
        )
        return 124  # GNU `timeout` convention (documented in --help)
    return int(proc.returncode)


@contextmanager
def _machine_lock() -> Generator[None]:
    """Hold a machine-wide non-blocking flock for the duration of the scan.

    Non-blocking is intentional: staged scans are bounded (<=90s in
    pre-commit) and full scans by ``--timeout``, so a busy lock means another
    scan is genuinely in progress — failing fast with a clear "retry" message
    avoids chaining waits that could themselves exceed the parent timeout.
    """
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_FILE, "a+")  # noqa: SIM115 - explicit close below
    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            raise _LockBusyError() from None
        yield
    finally:
        if acquired:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _run_full_scan(binary: str, source: Path, config: Path, timeout: float) -> int:
    """Run the full-mode scan (repo incl. history)."""
    command = build_gitleaks_command(binary, source, config)
    cwd = source if source.is_dir() else source.parent
    return _run_command_with_timeout(command, cwd, timeout)


def _run_staged_scan(binary: str, config: Path, timeout: float) -> int:
    """Run the staged-mode scan (staged file contents only, no history)."""
    paths = _staged_relative_paths()
    if not paths:
        # Nothing staged — nothing to scan. Fast exit before acquiring resources.
        return 0
    staging_dir = Path(tempfile.mkdtemp(prefix="narrare-gitleaks-staged-"))
    try:
        _materialize_staged_into(paths, staging_dir)
        command = build_staged_gitleaks_command(binary, staging_dir, config)
        return _run_command_with_timeout(command, staging_dir, timeout)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    """Run the Gitleaks secret-scanning gate."""
    args = parse_args(argv)
    binary_name = str(args.binary)
    config_arg = str(args.config)
    source_arg = str(args.source)
    timeout = float(args.timeout)

    binary = shutil.which(binary_name)
    if binary is None:
        print(_missing_binary_message(binary_name), file=sys.stderr)
        return 127  # POSIX "command not found" convention (documented in --help)

    config = Path(config_arg).expanduser().resolve()
    if not config.is_file():
        print(f"Gitleaks config not found: {config}", file=sys.stderr)
        return EXIT_WRAPPER_ERROR

    try:
        with _machine_lock():
            if args.staged:
                return _run_staged_scan(binary, config, timeout)
            source = Path(source_arg).expanduser().resolve()
            if not source.exists():
                print(f"Secret scan source does not exist: {source}", file=sys.stderr)
                return EXIT_WRAPPER_ERROR
            return _run_full_scan(binary, source, config, timeout)
    except _LockBusyError:
        print(
            "Another Narrare secret scan is already running on this machine "
            "(concurrency lock held). Retry your commit shortly.",
            file=sys.stderr,
        )
        return EXIT_LOCK_BUSY


if __name__ == "__main__":
    sys.exit(main())
