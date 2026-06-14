"""Tests for scripts/check_secrets.py — Gitleaks wrapper behavior."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.check_secrets as check_secrets  # noqa: E402


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
    assert exit_code == 127
    assert "Gitleaks binary not found" in captured.err
    assert "Install Gitleaks" in captured.err
    assert "just check-secrets" in captured.err


def test_main_invokes_gitleaks_with_required_secret_scan_flags(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Wrapper must invoke the mandatory CI/local Gitleaks gate flags."""
    config = tmp_path / ".gitleaks.toml"
    config.write_text("title = 'test'\n", encoding="utf-8")
    calls: list[tuple[list[str], Path | None, bool]] = []

    def fake_run(
        command: list[str],
        *,
        cwd: Path | None,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, cwd, check))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(check_secrets.shutil, "which", lambda _name: "/usr/local/bin/gitleaks")
    monkeypatch.setattr(check_secrets.subprocess, "run", fake_run)

    exit_code = check_secrets.main(["--source", str(tmp_path), "--config", str(config)])

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
            False,
        )
    ]
