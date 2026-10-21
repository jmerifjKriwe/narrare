#!/usr/bin/env python3
"""RAM-aware pytest-xdist worker selection for the `justfile` test recipes.

The tiers are a **contention guard**, not a fix for the worker-crash class.
On a machine with little available memory, running one worker per core makes
the suite slower (swap pressure, page-cache thrash) and each worker then
risks being killed by ``pytest-timeout`` at its 10 s deadline. Fewer workers
reduce that pressure. They do **not** prevent the timeout class itself: a
hanging test still hits ``pytest-timeout`` -> ``os._exit(1)``, and that crash
is a symptom of the hang, not evidence of an OOM kill.

Decision table (``choose_workers``)::

    available < 4096 MB   -> 1
    available < 12288 MB  -> 2
    otherwise             -> "auto"
    unknown (<= 0)        -> "auto"

The 12288 MB threshold is RULE-18 / Q-019 (measured ~2.4 GB/worker headroom
on 9.6 GB with 4 workers). Detection measures *available* RAM on Linux
(``/proc/meminfo``) but *total* RAM on macOS (``sysctl hw.memsize``), because
macOS has no portable available-memory metric; total is an overestimate.

Usage:
    uv run --no-sync python scripts/xdist_workers.py
"""

from __future__ import annotations

import subprocess  # nosec B404 - fixed argv, no shell
import sys
from pathlib import Path


class _RamTierLimits:
    """Memory tier boundaries in MB (configuration, not inline call-site values).

    RULE-18 treats ``*Limits`` classes as the configuration home for numeric
    policy values, so the tiers stay named and testable.
    """

    LOW_MEMORY_MB = 4096
    RAM_THRESHOLD_MB = 12288


MEMINFO_PATH = Path("/proc/meminfo")
BYTES_PER_MB = 1024 * 1024


def choose_workers(available_mb: int) -> int | str:
    """Map available memory (MB) to an xdist ``-n`` argument."""
    if available_mb <= 0:
        return "auto"
    if available_mb < _RamTierLimits.LOW_MEMORY_MB:
        return 1
    if available_mb < _RamTierLimits.RAM_THRESHOLD_MB:
        return 2
    return "auto"


def _meminfo_available_mb(path: Path) -> int:
    """Parse ``MemAvailable`` from a meminfo-format file; 0 when unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        # Converted to the documented "unknown" value, which yields "auto".
        return 0
    for line in text.splitlines():
        if not line.startswith("MemAvailable:"):
            continue
        parts = line.split()
        if len(parts) < 2:
            return 0
        try:
            return int(parts[1]) // 1024
        except ValueError:
            return 0
    return 0


def _sysctl_total_mb() -> int:
    """Total physical memory in MB via macOS ``sysctl``; 0 when unavailable."""
    try:
        result = subprocess.run(  # nosec B603  # fixed argv, no shell
            ["sysctl", "-n", "hw.memsize"],  # noqa: S607  # nosec B607  # macOS PATH lookup
            capture_output=True,
            check=True,
            text=True,
        )
    except OSError, subprocess.CalledProcessError:
        # Neither /proc/meminfo nor sysctl: documented "unknown" -> "auto".
        return 0
    try:
        return int(result.stdout.strip()) // BYTES_PER_MB
    except ValueError:
        return 0


def available_mb(meminfo_path: Path = MEMINFO_PATH) -> int:
    """Available memory in MB, or 0 when the platform has no readable source."""
    if meminfo_path.is_file():
        return _meminfo_available_mb(meminfo_path)
    return _sysctl_total_mb()


def main() -> int:
    print(choose_workers(available_mb()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
