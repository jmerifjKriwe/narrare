"""Unit tests for scripts/check_adr_naming.py (review-04 AUFG-04-10)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"


def _load_module():
    """Load check_adr_naming.py as a module (it lives outside a package)."""
    spec = importlib.util.spec_from_file_location(
        "check_adr_naming", _SCRIPTS_DIR / "check_adr_naming.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_adr_naming"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def checker():
    return _load_module()


@pytest.fixture()
def decisions_dir(tmp_path: Path) -> Path:
    """Build a minimal decisions directory with the canonical files."""
    d = tmp_path / "docs" / "architecture" / "decisions"
    d.mkdir(parents=True)
    return d


def test_clean_directory_passes(checker, decisions_dir: Path) -> None:
    """A directory where every ADR follows the convention passes."""
    (decisions_dir / "ADR-001-llm-gateway.md").touch()
    (decisions_dir / "ADR-063-deterministic-ci-venv-contract.md").touch()
    (decisions_dir / "INDEX.md").touch()
    (decisions_dir / "_TEMPLATE.md").touch()
    assert checker.find_violations(decisions_dir) == []
    assert checker.main(["--decisions-dir", str(decisions_dir)]) == 0


def test_prefixless_file_is_flagged(checker, decisions_dir: Path) -> None:
    """The legacy ``XXX-name.md`` form produces a precise rename hint."""
    (decisions_dir / "ADR-001-foo.md").touch()
    (decisions_dir / "099-bad-name.md").touch()
    violations = checker.find_violations(decisions_dir)
    assert len(violations) == 1
    v = violations[0]
    assert "ADR-099-bad-name.md" in v.detail
    assert "git mv" in v.detail
    assert checker.main(["--decisions-dir", str(decisions_dir)]) == 1


def test_index_and_template_are_exempt(checker, decisions_dir: Path) -> None:
    """INDEX.md and _TEMPLATE.md never count as ADRs."""
    (decisions_dir / "INDEX.md").touch()
    (decisions_dir / "_TEMPLATE.md").touch()
    assert checker.find_violations(decisions_dir) == []


def test_subdirectories_are_skipped(checker, decisions_dir: Path) -> None:
    """Files in subdirectories (e.g. ``discussions/``) are out of scope."""
    sub = decisions_dir / "discussions"
    sub.mkdir()
    (sub / "some-note.md").touch()
    (decisions_dir / "ADR-001-foo.md").touch()
    assert checker.find_violations(decisions_dir) == []


def test_non_md_files_skipped(checker, decisions_dir: Path) -> None:
    """A stray non-markdown file does not trip the checker."""
    (decisions_dir / "ADR-001-foo.md").touch()
    (decisions_dir / "notes.txt").touch()
    assert checker.find_violations(decisions_dir) == []


def test_unrecognised_md_gets_generic_message(checker, decisions_dir: Path) -> None:
    """An .md file that is neither exempt nor ADR-shaped gets a clear message."""
    (decisions_dir / "random.md").touch()
    violations = checker.find_violations(decisions_dir)
    assert len(violations) == 1
    assert "EXEMPT_BASENAMES" in violations[0].detail


def test_json_output(checker, decisions_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (decisions_dir / "ADR-001-foo.md").touch()
    (decisions_dir / "099-bad.md").touch()
    rc = checker.main(["--decisions-dir", str(decisions_dir), "--json"])
    assert rc == 1
    out = capsys.readouterr().out
    assert '"passed": false' in out
    assert "099-bad.md" in out


def test_missing_directory_returns_empty(checker, tmp_path: Path) -> None:
    """A non-existent directory is out of scope — not a checker error."""
    missing = tmp_path / "does-not-exist"
    assert checker.find_violations(missing) == []
