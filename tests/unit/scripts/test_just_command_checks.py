"""Unit tests for scripts/doc_drift/just_command_checks.py (review-04 AUFG-04-02/04).

The just-recipe drift check scans markdown docs for ``just <recipe>``
references and flags recipes absent from the real justfile set. Tests
cover recipe extraction, phantom detection, negation exclusions,
excluded directories, superseded-ADR skipping, and integration via
``check_just_command_drift()``.

See: review-04-dx-tooling.md AUFG-04-02 / AUFG-04-04.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load_module():
    """Load just_command_checks via the doc_drift package import path."""
    sys.path.insert(0, str(_SCRIPTS_DIR))
    try:
        # Force a fresh import so module-level constants resolve correctly.
        # Pop the WHOLE doc_drift family (see test_agent_name_checks for the
        # orphaned-sys.modules rationale).
        for name in [
            n for n in list(sys.modules) if n == "doc_drift" or n.startswith("doc_drift.")
        ]:
            sys.modules.pop(name, None)
        import doc_drift.just_command_checks as mod  # type: ignore[import-not-found]

        return mod
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(_SCRIPTS_DIR))


@pytest.fixture()
def checker():
    return _load_module()


# ── Recipe extraction (_parse_justfile) ────────────────────────


class TestParseJustfile:
    """Recipe-name extraction from justfile text."""

    def test_basic_recipes(self, checker, tmp_path: Path) -> None:
        jf = tmp_path / "justfile"
        jf.write_text("dev:\n    echo hi\ntest:\n    pytest\n", encoding="utf-8")
        recipes = checker._parse_justfile(jf)
        assert "dev" in recipes
        assert "test" in recipes

    def test_set_directive_excluded(self, checker, tmp_path: Path) -> None:
        """`set shell := [...]` is a setting, not a recipe."""
        jf = tmp_path / "justfile"
        jf.write_text("set shell := ['bash']\ndev:\n    echo hi\n", encoding="utf-8")
        recipes = checker._parse_justfile(jf)
        assert "dev" in recipes
        assert "set" not in recipes

    def test_recipe_with_params(self, checker, tmp_path: Path) -> None:
        jf = tmp_path / "justfile"
        jf.write_text("db-revision msg:\n    alembic\n", encoding="utf-8")
        assert "db-revision" in checker._parse_justfile(jf)

    def test_indented_body_not_a_recipe(self, checker, tmp_path: Path) -> None:
        jf = tmp_path / "justfile"
        jf.write_text("dev:\n    echo hi\n", encoding="utf-8")
        assert "echo" not in checker._parse_justfile(jf)

    def test_missing_file_returns_empty(self, checker, tmp_path: Path) -> None:
        assert checker._parse_justfile(tmp_path / "nope") == frozenset()


# ── get_real_recipes (real justfile / just CLI) ────────────────


def test_get_real_recipes_contains_known(checker) -> None:
    recipes = checker.get_real_recipes()
    assert recipes  # non-empty
    assert "dev" in recipes
    assert "test" in recipes
    assert "check" in recipes


# ── _scan_file (phantom detection + negation) ──────────────────


class TestScanFile:
    """Single-file scanning: phantoms flagged, valid recipes clean."""

    def test_phantom_recipe_is_critical(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Run `just dev-up` now.\n", encoding="utf-8")
        findings = checker._scan_file(f, frozenset({"dev"}))
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "JUST-CMD-DRIFT" in findings[0].message
        assert "dev-up" in findings[0].message

    def test_valid_recipe_no_finding(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Run `just dev` now.\n", encoding="utf-8")
        assert checker._scan_file(f, frozenset({"dev"})) == []

    def test_duplicate_phantom_deduped_per_file(self, checker, tmp_path: Path) -> None:
        f = tmp_path / "doc.md"
        f.write_text("Run `just ghost` then `just ghost` again.\n", encoding="utf-8")
        findings = checker._scan_file(f, frozenset({"dev"}))
        assert len(findings) == 1
        assert "ghost" in findings[0].message

    def test_missing_file_returns_empty(self, checker, tmp_path: Path) -> None:
        assert checker._scan_file(tmp_path / "nope.md", frozenset()) == []


# ── Negation exclusions ────────────────────────────────────────


@pytest.mark.parametrize(
    "line",
    [
        "No `just ghost` exists.",
        "Do not `just ghost`.",
        "without `just ghost`.",
        "there is no `just ghost`.",
        "`just ghost` does not exist.",
        "`just ghost` doesn't exist.",
        "`just ghost` is a recipe to be added.",
    ],
)
def test_negation_variants_skipped(checker, tmp_path: Path, line: str) -> None:
    """Explanatory text (command does NOT exist) must not false-positive."""
    f = tmp_path / "d.md"
    f.write_text(line + "\n", encoding="utf-8")
    assert checker._scan_file(f, frozenset({"dev"})) == []


def test_actionable_phantom_on_separate_line_flagged(checker, tmp_path: Path) -> None:
    """A negation line does not shield a phantom on a different line."""
    f = tmp_path / "d.md"
    f.write_text("No `just ghost`.\nRun `just phantom` instead.\n", encoding="utf-8")
    findings = checker._scan_file(f, frozenset({"dev"}))
    assert len(findings) == 1
    assert "phantom" in findings[0].message


# ── Excluded directories ───────────────────────────────────────


class TestExcludedDir:
    def test_archive_excluded(self, checker) -> None:
        assert checker._is_excluded_dir(Path("archive") / "old.md")

    def test_superpowers_plans_excluded(self, checker) -> None:
        assert checker._is_excluded_dir(Path("superpowers") / "plans" / "plan.md")

    def test_development_not_excluded(self, checker) -> None:
        assert not checker._is_excluded_dir(Path("development") / "guide.md")


# ── Superseded ADR ─────────────────────────────────────────────


def test_superseded_adr_detected(checker, tmp_path: Path) -> None:
    f = tmp_path / "ADR-001-x.md"
    f.write_text(
        "# ADR-001\n\n> **Status:** ⛔ Superseded by ADR-002\n",
        encoding="utf-8",
    )
    assert checker._is_superseded_adr(f)


def test_deprecated_adr_detected(checker, tmp_path: Path) -> None:
    f = tmp_path / "ADR-002-x.md"
    f.write_text("# ADR-002\n\n> **Status:** 🗄️ Deprecated\n", encoding="utf-8")
    assert checker._is_superseded_adr(f)


def test_active_adr_not_superseded(checker, tmp_path: Path) -> None:
    f = tmp_path / "ADR-003-x.md"
    f.write_text("# ADR-003\n\n> **Status:** ✅ Accepted\n", encoding="utf-8")
    assert not checker._is_superseded_adr(f)


# ── Integration: check_just_command_drift ──────────────────────


def test_clean_docs_no_findings(checker, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(checker, "get_real_recipes", lambda: frozenset({"dev", "test"}))
    (tmp_path / "guide.md").write_text("Use `just dev` and `just test`.\n", encoding="utf-8")
    assert checker.check_just_command_drift(docs_dir=tmp_path) == []


def test_phantom_in_nested_dir(checker, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(checker, "get_real_recipes", lambda: frozenset({"dev"}))
    sub = tmp_path / "dev" / "deep"
    sub.mkdir(parents=True)
    (sub / "guide.md").write_text("Run `just ghost`.\n", encoding="utf-8")
    findings = checker.check_just_command_drift(docs_dir=tmp_path)
    assert any("ghost" in f.message for f in findings)


def test_archive_dir_skipped(checker, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(checker, "get_real_recipes", lambda: frozenset({"dev"}))
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "old.md").write_text("Run `just ghost`.\n", encoding="utf-8")
    assert checker.check_just_command_drift(docs_dir=tmp_path) == []


def test_superseded_adr_skipped(checker, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(checker, "get_real_recipes", lambda: frozenset({"dev"}))
    (tmp_path / "ADR-001-x.md").write_text(
        "# ADR-001\n\n> **Status:** ⛔ Superseded by ADR-002\n\nRun `just ghost`.\n",
        encoding="utf-8",
    )
    assert checker.check_just_command_drift(docs_dir=tmp_path) == []


def test_empty_recipe_set_returns_warning(checker, monkeypatch: pytest.MonkeyPatch) -> None:
    """When no recipes can be extracted, warn instead of flagging everything."""
    monkeypatch.setattr(checker, "get_real_recipes", lambda: frozenset())
    findings = checker.check_just_command_drift()
    assert len(findings) == 1
    assert findings[0].severity == "warning"
