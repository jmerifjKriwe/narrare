"""Tests for frontmatter-aware file-reference checking in spec_checks.

Background:
    The spec-checker's ``_check_file_path_references`` validates every
    backtick-wrapped path in a feature spec against the filesystem. Specs
    with a frontmatter ``status:`` of ``planned``, ``idea``, or
    ``deprecated`` are *design documents* — their referenced paths are
    intentional aspirations and need not exist yet. Validating them
    produced hundreds of false-positive warnings.

    These tests pin the agreed behaviour (ADR-041 Decision 2 follow-up):
    the file-reference check is *skipped* for specs whose frontmatter
    status is in ``{planned, idea, deprecated}``, and *runs* for every
    other status (including the absence of frontmatter).

See: ADR-041 Decision 2.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from doc_drift.spec_checks import (  # noqa: E402
    _check_file_path_references,
    _extract_spec_status,
)

if TYPE_CHECKING:
    from doc_drift.adr_checks import DocDriftFinding


# ── Tiny local fixtures (self-contained, RULE-06) ──────────────


def _make_spec_file(tmp_path: Path, filename: str, content: str) -> Path:
    """Write a mock spec file into a ``specs`` subdir of ``tmp_path``."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir(exist_ok=True)
    p = spec_dir / filename
    p.write_text(content, encoding="utf-8")
    return p


def _spec_referencing_missing_file(status_block: str) -> str:
    """Build a spec body that references a non-existent file.

    Args:
        status_block: Either a YAML frontmatter block (ending with ``---\\n``)
            or an empty string (no frontmatter).
    """
    return (
        f"{status_block}# Test Spec\n\nSee `nonexistent/future_module.py` for the implementation.\n"
    )


def _file_ref_findings(specs: list[Path]) -> list[DocDriftFinding]:
    """Run only the file-path sub-check; filter to file-reference findings."""
    findings = _check_file_path_references(specs)
    return [f for f in findings if "References file" in f.message]


# ── _extract_spec_status unit tests ────────────────────────────


class TestExtractSpecStatus:
    """Unit tests for the frontmatter status extraction helper."""

    def test_extracts_planned(self) -> None:
        content = "---\nstatus: planned\ntitle: Foo\n---\n\n# Body\n"
        assert _extract_spec_status(content) == "planned"

    def test_extracts_idea(self) -> None:
        content = "---\nstatus: idea\n---\n\n# Body\n"
        assert _extract_spec_status(content) == "idea"

    def test_extracts_deprecated(self) -> None:
        content = "---\nstatus: deprecated\n---\n\n# Body\n"
        assert _extract_spec_status(content) == "deprecated"

    def test_extracts_implemented(self) -> None:
        content = "---\nstatus: implemented\n---\n\n# Body\n"
        assert _extract_spec_status(content) == "implemented"

    def test_normalizes_whitespace_and_case(self) -> None:
        content = "---\nstatus:   Planned  \ntitle: Foo\n---\n\n# Body\n"
        assert _extract_spec_status(content) == "planned"

    def test_no_frontmatter_returns_none(self) -> None:
        """Specs using blockquote status (no YAML frontmatter) → None.

        Regression guard: many specs use ``> **Status:** implemented`` rather
        than YAML frontmatter. These must return ``None`` so they keep being
        checked (they claim existence).
        """
        content = "# Title\n\n> **Status:** implemented\n"
        assert _extract_spec_status(content) is None

    def test_frontmatter_without_status_returns_none(self) -> None:
        content = "---\ntitle: Foo\narea: writing\n---\n\n# Body\n"
        assert _extract_spec_status(content) is None

    def test_status_word_in_body_ignored(self) -> None:
        """A ``status:`` word appearing only in the body must be ignored."""
        content = "---\ntitle: Foo\n---\n\nThe status: stable applies here.\n"
        assert _extract_spec_status(content) is None

    def test_frontmatter_status_wins_over_body(self) -> None:
        """Frontmatter status wins; a later body line does not override."""
        content = "---\nstatus: planned\n---\n\nSome note with status: implemented in prose.\n"
        assert _extract_spec_status(content) == "planned"


# ── File-reference skip behaviour (Tests A-F) ──────────────────
#
# These exercise ``_check_file_path_references`` directly to isolate the
# frontmatter-status gating from the rule/ADR sub-checks.


class TestSkipStatusesNoWarning:
    """Specs whose frontmatter status is aspirational must NOT be flagged."""

    def test_status_planned_no_warning(self, tmp_path: Path) -> None:
        # Test A
        spec = _make_spec_file(
            tmp_path,
            "planned-spec.md",
            _spec_referencing_missing_file("---\nstatus: planned\n---\n\n"),
        )
        findings = _file_ref_findings([spec])
        assert findings == [], f"Expected no warning for planned spec, got {findings}"

    def test_status_idea_no_warning(self, tmp_path: Path) -> None:
        # Test E
        spec = _make_spec_file(
            tmp_path,
            "idea-spec.md",
            _spec_referencing_missing_file("---\nstatus: idea\n---\n\n"),
        )
        findings = _file_ref_findings([spec])
        assert findings == [], f"Expected no warning for idea spec, got {findings}"

    def test_status_deprecated_no_warning(self, tmp_path: Path) -> None:
        # Test F
        spec = _make_spec_file(
            tmp_path,
            "deprecated-spec.md",
            _spec_referencing_missing_file("---\nstatus: deprecated\n---\n\n"),
        )
        findings = _file_ref_findings([spec])
        assert findings == [], f"Expected no warning for deprecated spec, got {findings}"


class TestCheckedStatusesDoWarn:
    """Specs claiming existence (implemented/done/stable) must still be flagged."""

    def test_status_implemented_warns(self, tmp_path: Path) -> None:
        # Test B
        spec = _make_spec_file(
            tmp_path,
            "implemented-spec.md",
            _spec_referencing_missing_file("---\nstatus: implemented\n---\n\n"),
        )
        findings = _file_ref_findings([spec])
        assert any("future_module.py" in f.message and f.severity == "warning" for f in findings), (
            f"Expected warning for implemented spec, got {findings}"
        )

    def test_status_done_warns(self, tmp_path: Path) -> None:
        # Test C
        spec = _make_spec_file(
            tmp_path,
            "done-spec.md",
            _spec_referencing_missing_file("---\nstatus: done\n---\n\n"),
        )
        findings = _file_ref_findings([spec])
        assert any("future_module.py" in f.message for f in findings), (
            f"Expected warning for done spec, got {findings}"
        )

    def test_status_stable_warns(self, tmp_path: Path) -> None:
        """Sanity: 'stable' is not a skip status — it must be checked."""
        spec = _make_spec_file(
            tmp_path,
            "stable-spec.md",
            _spec_referencing_missing_file("---\nstatus: stable\n---\n\n"),
        )
        findings = _file_ref_findings([spec])
        assert any("future_module.py" in f.message for f in findings), (
            f"Expected warning for stable spec, got {findings}"
        )


class TestDefaultBehaviourPreserved:
    """Specs without YAML frontmatter are still checked (default behaviour)."""

    def test_no_frontmatter_warns(self, tmp_path: Path) -> None:
        # Test D
        spec = _make_spec_file(
            tmp_path,
            "no-frontmatter-spec.md",
            _spec_referencing_missing_file(""),
        )
        findings = _file_ref_findings([spec])
        assert any("future_module.py" in f.message for f in findings), (
            f"Expected warning for spec without frontmatter, got {findings}"
        )

    def test_blockquote_status_still_warns(self, tmp_path: Path) -> None:
        """Blockquote status (no YAML) is not a skip — still checked."""
        content = (
            "# Spec\n\n> **Status:** planned\n\nSee `nonexistent/future_module.py` for impl.\n"
        )
        spec = _make_spec_file(tmp_path, "blockquote-spec.md", content)
        findings = _file_ref_findings([spec])
        assert any("future_module.py" in f.message for f in findings), (
            f"Expected warning for blockquote-status spec, got {findings}"
        )
