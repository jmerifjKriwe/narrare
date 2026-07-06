"""Unit tests for scripts/check_context_freshness.py (review-04 AUFG-04-14).

Covers the staleness gate: a context file's declared ``Updated:`` date must
not be implausibly old. Hard-fail at 60 days, warn at 30.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "check_context_freshness", _SCRIPTS_DIR / "check_context_freshness.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_context_freshness"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def checker():
    return _load_module()


@pytest.fixture()
def context_dir(tmp_path: Path) -> Path:
    d = tmp_path / "context"
    d.mkdir()
    return d


def _write(path: Path, updated: str) -> None:
    path.write_text(f"---\nUpdated: {updated}\n---\nbody\n", encoding="utf-8")


def test_fresh_file_passes(checker, context_dir: Path) -> None:
    today = dt.date.today()
    _write(context_dir / "fresh.md", today.isoformat())
    assert checker.find_findings(context_dir) == []
    assert checker.main(["--context-dir", str(context_dir)]) == 0


def test_file_without_updated_is_skipped(checker, context_dir: Path) -> None:
    """Freshness is opt-in via the frontmatter; no field = not checked."""
    (context_dir / "no-frontmatter.md").write_text("just body\n", encoding="utf-8")
    assert checker.find_findings(context_dir) == []


def test_warning_band_between_30_and_60_days(checker, context_dir: Path) -> None:
    today = dt.date.today()
    declared = today - dt.timedelta(days=40)  # > 30, < 60
    _write(context_dir / "stale.md", declared.isoformat())
    findings = checker.find_findings(context_dir)
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    # Warnings do not fail CI
    assert checker.main(["--context-dir", str(context_dir)]) == 0


def test_critical_over_60_days(checker, context_dir: Path) -> None:
    today = dt.date.today()
    declared = today - dt.timedelta(days=90)  # > 60
    _write(context_dir / "very-stale.md", declared.isoformat())
    findings = checker.find_findings(context_dir)
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert checker.main(["--context-dir", str(context_dir)]) == 1


def test_future_dated_file_is_not_a_finding(checker, context_dir: Path) -> None:
    today = dt.date.today()
    declared = today + dt.timedelta(days=5)
    _write(context_dir / "future.md", declared.isoformat())
    assert checker.find_findings(context_dir) == []


def test_malformed_date_is_skipped(checker, context_dir: Path) -> None:
    (context_dir / "bad.md").write_text("---\nUpdated: not-a-date\n---\n", encoding="utf-8")
    assert checker.find_findings(context_dir) == []


def test_custom_thresholds_override_defaults(checker, context_dir: Path) -> None:
    today = dt.date.today()
    # 20 days old: under default warn threshold (30) but over a custom 10
    _write(context_dir / "mid.md", (today - dt.timedelta(days=20)).isoformat())
    findings = checker.find_findings(context_dir, max_age_days=100, warn_age_days=10)
    assert len(findings) == 1
    assert findings[0].severity == "warning"


def test_nested_files_scanned(checker, tmp_path: Path) -> None:
    """The checker recurses into subdirectories."""
    today = dt.date.today()
    nested_dir = tmp_path / "context" / "lookup"
    nested_dir.mkdir(parents=True)
    _write(nested_dir / "deep.md", (today - dt.timedelta(days=90)).isoformat())
    findings = checker.find_findings(tmp_path / "context")
    assert len(findings) == 1
    assert findings[0].severity == "critical"


def test_json_output(checker, context_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    today = dt.date.today()
    _write(context_dir / "old.md", (today - dt.timedelta(days=90)).isoformat())
    rc = checker.main(["--context-dir", str(context_dir), "--json"])
    assert rc == 1
    out = capsys.readouterr().out
    assert '"passed": false' in out
    assert "critical" in out
