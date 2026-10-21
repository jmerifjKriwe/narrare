"""Tests for scripts/xdist_workers.py — RAM-aware xdist worker tiers.

The tiers are a contention guard only; they do not prevent the
pytest-timeout worker-crash class (T21a).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.xdist_workers import (  # noqa: E402
    available_mb,
    choose_workers,
)

# ---------------------------------------------------------------------------
# choose_workers tiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("available_mb_value", "expected"),
    [
        pytest.param(0, "auto", id="zero-is-unknown"),
        pytest.param(1024, 1, id="1gb"),
        pytest.param(4095, 1, id="just-below-4gb"),
        pytest.param(4096, 2, id="4gb-boundary"),
        pytest.param(12287, 2, id="just-below-12gb"),
        pytest.param(12288, "auto", id="12gb-boundary"),
        pytest.param(65536, "auto", id="64gb"),
    ],
)
def test_choose_workers_tiers(available_mb_value: int, expected: int | str) -> None:
    assert choose_workers(available_mb_value) == expected


def test_choose_workers_negative_is_unknown() -> None:
    assert choose_workers(-1) == "auto"


# ---------------------------------------------------------------------------
# available_mb parser
# ---------------------------------------------------------------------------


def test_available_mb_reads_memavailable_kb(tmp_path: Path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       16384000 kB\nMemFree:         1000000 kB\nMemAvailable:    8388608 kB\n",
        encoding="utf-8",
    )

    assert available_mb(meminfo) == 8192


def test_available_mb_missing_key_returns_zero(tmp_path: Path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal: 16384000 kB\n", encoding="utf-8")

    assert available_mb(meminfo) == 0


def test_available_mb_invalid_value_returns_zero(tmp_path: Path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable: not-a-number kB\n", encoding="utf-8")

    assert available_mb(meminfo) == 0


def test_available_mb_unreadable_path_falls_back_to_sysctl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "does-not-exist"

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("sysctl unavailable")

    monkeypatch.setattr("scripts.xdist_workers.subprocess.run", fake_run)

    assert available_mb(missing) == 0


def test_available_mb_unreadable_path_uses_sysctl_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "does-not-exist"

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="17179869184", stderr="")

    monkeypatch.setattr("scripts.xdist_workers.subprocess.run", fake_run)

    # 17179869184 bytes // 1048576 == 16384 MB
    assert available_mb(missing) == 16384


def test_available_mb_default_reads_module_meminfo_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable:    2097152 kB\n", encoding="utf-8")
    monkeypatch.setattr("scripts.xdist_workers.MEMINFO_PATH", meminfo)

    assert available_mb() == 2048


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_prints_valid_token() -> None:
    result = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "xdist_workers.py")],
        capture_output=True,
        check=True,
        text=True,
    )

    assert result.stdout.strip() in {"1", "2", "auto"}
