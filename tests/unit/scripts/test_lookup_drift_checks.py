"""Unit tests for scripts/doc_drift/lookup_drift_checks.py (review-04 AUFG-04-13).

The lookup drift checks detect known drift patterns in extracted context
files. Patterns must match real drift (pins, phantom commands) and NOT
match legitimate negations ("fastapi-limiter is not used", "No `just dev-up`").
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load_module():
    """Load lookup_drift_checks via the doc_drift package import path."""
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        # Force a fresh import so REPO_ROOT/_LOOKUP_DIR resolve correctly.
        for name in [
            "doc_drift",
            "doc_drift.lookup_drift_checks",
        ]:
            sys.modules.pop(name, None)
        import doc_drift.lookup_drift_checks as mod  # type: ignore[import-not-found]

        return mod
    finally:
        # Leave sys.path clean for other tests.
        with contextlib.suppress(ValueError):
            sys.path.remove(str(_SCRIPTS_DIR))


@pytest.fixture()
def checker():
    return _load_module()


@pytest.fixture()
def lookup_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Build a fake .opencode/context/narrare-dev/ tree.

    Returns the lookup dir and repoints the module's _LOOKUP_DIR at it so
    patterns resolve against controlled fixture files.
    """
    narrare_dev = tmp_path / ".opencode" / "context" / "narrare-dev"
    narrare_dev.mkdir(parents=True)
    return narrare_dev


def _repointer(checker, lookup_dir: Path) -> None:

    # Build a fresh module with _LOOKUP_DIR pointed at the fixture dir.
    # Simpler: mutate the module global in place.
    checker._LOOKUP_DIR = lookup_dir


def test_clean_lookup_files_have_no_findings(checker, lookup_tree: Path) -> None:
    _repointer(checker, lookup_tree)
    (lookup_tree / "lookup").mkdir()
    (lookup_tree / "guides").mkdir()
    (lookup_tree / "processes").mkdir()
    (lookup_tree / "lookup" / "tech-stack.md").write_text(
        "# tech stack\nSee packages/core/pyproject.toml for pydantic-ai (v2.x).\n",
        encoding="utf-8",
    )
    (lookup_tree / "guides" / "deployment.md").write_text(
        "# deployment\nNo `just dev-up` — use `just dev-services`.\n",
        encoding="utf-8",
    )
    (lookup_tree / "processes" / "quality-gates.md").write_text(
        "# gates\nCoverage floor: 80% (--cov-fail-under=80).\n",
        encoding="utf-8",
    )
    assert checker.check_lookup_drift() == []


def test_pydantic_ai_1x_pin_is_critical(checker, lookup_tree: Path) -> None:
    _repointer(checker, lookup_tree)
    (lookup_tree / "lookup").mkdir(parents=True)
    (lookup_tree / "lookup" / "tech-stack.md").write_text("pydantic-ai >=1.93\n", encoding="utf-8")
    findings = checker.check_lookup_drift()
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert "LOOKUP-PYDANTIC-AI-1X" in findings[0].message


def test_mem0_1x_pin_is_critical(checker, lookup_tree: Path) -> None:
    _repointer(checker, lookup_tree)
    (lookup_tree / "lookup").mkdir(parents=True)
    (lookup_tree / "lookup" / "tech-stack.md").write_text("mem0 >=1.0\n", encoding="utf-8")
    findings = checker.check_lookup_drift()
    assert any(f.severity == "critical" and "LOOKUP-MEM0-1X" in f.message for f in findings)


def test_fastapi_limiter_pin_is_critical(checker, lookup_tree: Path) -> None:
    _repointer(checker, lookup_tree)
    (lookup_tree / "lookup").mkdir(parents=True)
    (lookup_tree / "lookup" / "tech-stack.md").write_text(
        "fastapi-limiter >=0.1.6\n", encoding="utf-8"
    )
    findings = checker.check_lookup_drift()
    assert any("LOOKUP-FASTAPI-LIMITER" in f.message for f in findings)


def test_fastapi_limiter_negation_not_flagged(checker, lookup_tree: Path) -> None:
    """A 'fastapi-limiter is not used' note must NOT trigger."""
    _repointer(checker, lookup_tree)
    (lookup_tree / "lookup").mkdir(parents=True)
    (lookup_tree / "lookup" / "tech-stack.md").write_text(
        "fastapi-limiter is **not** used (unmaintained).\n",
        encoding="utf-8",
    )
    findings = checker.check_lookup_drift()
    assert not any("LOOKUP-FASTAPI-LIMITER" in f.message for f in findings)


def test_phantom_dev_up_actionable_is_critical(checker, lookup_tree: Path) -> None:
    _repointer(checker, lookup_tree)
    (lookup_tree / "guides").mkdir(parents=True)
    (lookup_tree / "guides" / "deployment.md").write_text(
        "Run `just dev-up` first.\n", encoding="utf-8"
    )
    findings = checker.check_lookup_drift()
    assert any("LOOKUP-PHANTOM-DEV-UP" in f.message for f in findings)


def test_phantom_dev_up_negation_not_flagged(checker, lookup_tree: Path) -> None:
    """'No `just dev-up`' is a legitimate clarification, not a phantom."""
    _repointer(checker, lookup_tree)
    (lookup_tree / "guides").mkdir(parents=True)
    (lookup_tree / "guides" / "deployment.md").write_text(
        "> **No `just dev-up`.** There is no separate dev-up recipe.\n",
        encoding="utf-8",
    )
    findings = checker.check_lookup_drift()
    assert not any("LOOKUP-PHANTOM-DEV-UP" in f.message for f in findings)


def test_60_percent_coverage_floor_is_critical(checker, lookup_tree: Path) -> None:
    _repointer(checker, lookup_tree)
    (lookup_tree / "processes").mkdir(parents=True)
    (lookup_tree / "processes" / "quality-gates.md").write_text(
        "Hard floor: 60%\n", encoding="utf-8"
    )
    findings = checker.check_lookup_drift()
    assert any("LOOKUP-COVERAGE-60-FLOOR" in f.message for f in findings)


def test_hardcoded_hook_count_is_warning(checker, lookup_tree: Path) -> None:
    _repointer(checker, lookup_tree)
    (lookup_tree / "guides").mkdir(parents=True)
    (lookup_tree / "guides" / "deployment.md").write_text(
        "Pre-commit has 9 hooks.\n", encoding="utf-8"
    )
    findings = checker.check_lookup_drift()
    warnings = [f for f in findings if f.severity == "warning"]
    assert any("LOOKUP-HOOK-COUNT" in f.message for f in warnings)


def test_missing_file_skips_pattern(checker, lookup_tree: Path) -> None:
    """If the lookup file does not exist, the pattern is skipped (no finding)."""
    _repointer(checker, lookup_tree)
    # No files created at all.
    assert checker.check_lookup_drift() == []


def test_multiple_findings_in_one_file(checker, lookup_tree: Path) -> None:
    """A file with several drift patterns produces several findings."""
    _repointer(checker, lookup_tree)
    (lookup_tree / "lookup").mkdir(parents=True)
    (lookup_tree / "lookup" / "tech-stack.md").write_text(
        "pydantic-ai >=1.93\nmem0 >=1.0\nfastapi-limiter >=0.1.6\n",
        encoding="utf-8",
    )
    findings = checker.check_lookup_drift()
    # Extract the CHECK_ID token (e.g. "LOOKUP-PYDANTIC-AI-1X") from each message.
    ids = {f.message.split("]")[0].split("[")[-1] for f in findings}
    assert "LOOKUP-PYDANTIC-AI-1X" in ids
    assert "LOOKUP-MEM0-1X" in ids
    assert "LOOKUP-FASTAPI-LIMITER" in ids
