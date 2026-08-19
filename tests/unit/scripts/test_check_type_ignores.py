"""Tests for scripts/check_type_ignores/scanner.py — tokenized suppression scan.

Regression coverage for the docstring/prose false-positive fix: only lines
whose ``# type: ignore`` marker lives in an actual COMMENT token count as
suppressions; STRING-token occurrences (docstrings, literals) are prose and
must be ignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.check_type_ignores.scanner as scanner_mod  # noqa: E402
from scripts.check_type_ignores.scanner import (  # noqa: E402
    ScanResult,
    _scan_single_file,
    comment_marker_lines,
    scan_codebase,
)

# ---------------------------------------------------------------------------
# comment_marker_lines
# ---------------------------------------------------------------------------


class TestCommentMarkerLines:
    """Tokenize-based detection of real comment suppressions."""

    def test_real_comment_is_marked(self) -> None:
        src = "x = foo()  # type: ignore[arg-type]\n"
        assert comment_marker_lines(src) == {1}

    def test_naked_comment_is_marked(self) -> None:
        src = "x = foo()  # type: ignore\n"
        assert comment_marker_lines(src) == {1}

    def test_docstring_prose_is_not_marked(self) -> None:
        src = (
            "def f():\n"
            '    """Doc.\n\n'
            "    Implement this without ``# type: ignore`` (RULE-23). The\n"
            "    contract below explains why.\n"
            '    """\n'
            "    return 1\n"
        )
        assert comment_marker_lines(src) == set()

    def test_string_literal_prose_is_not_marked(self) -> None:
        src = 'msg = "never write # type: ignore in strings"\n'
        assert comment_marker_lines(src) == set()

    def test_fstring_prose_is_not_marked(self) -> None:
        src = 'msg = f"avoid # type: ignore here"\n'
        assert comment_marker_lines(src) == set()

    def test_mixed_line_counts_only_comment(self) -> None:
        # Prose in a string AND a real suppression comment on the same line.
        src = 'x = "mentions # type: ignore"  # type: ignore[arg-type]\n'
        assert comment_marker_lines(src) == {1}

    def test_multiline_docstring_with_bracketed_prose(self) -> None:
        src = (
            "class C:\n"
            '    """Docs.\n\n'
            "    Do not use ``# type: ignore[arg-type]`` for mocks.\n"
            '    """\n'
        )
        assert comment_marker_lines(src) == set()

    def test_untokenizable_source_returns_none(self) -> None:
        # Unterminated triple-quoted string → TokenError → fallback signal.
        src = 'x = """unterminated\n'
        assert comment_marker_lines(src) is None


# ---------------------------------------------------------------------------
# _scan_single_file (integration of the marker filter)
# ---------------------------------------------------------------------------


def _scan_as_production(
    monkeypatch, tmp_path: Path, content: str, filename: str = "sample.py"
) -> ScanResult:
    """Write *content* under *tmp_path* and scan it as a production file.

    ``PRODUCTION_PREFIXES`` is monkeypatched to the temp directory because
    the scanner categorizes by absolute path prefix.
    """
    target = tmp_path / "apps" / "api" / "narrare" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    monkeypatch.setattr(
        scanner_mod, "PRODUCTION_PREFIXES", (str(tmp_path / "apps" / "api" / "narrare"),)
    )

    result = ScanResult()
    _scan_single_file(target, result)
    return result


class TestScanSingleFileProseExclusion:
    """Docstring prose must not appear in production counts."""

    def test_docstring_prose_not_counted_as_suppression(self, monkeypatch, tmp_path: Path) -> None:
        content = (
            '"""Module doc.\n\n'
            "Implement just these two methods without ``# type: ignore``\n"
            "(RULE-23). The contract below explains why.\n"
            '"""\n\n'
            "VALUE = 1\n"
        )
        result = _scan_as_production(monkeypatch, tmp_path, content)
        assert result.total == 0
        assert result.production_total == 0
        assert result.uncommented_ignores == []

    def test_real_suppression_still_counted(self, monkeypatch, tmp_path: Path) -> None:
        content = '"""Module doc."""\n\nx = foo()  # type: ignore[arg-type]\n'
        result = _scan_as_production(monkeypatch, tmp_path, content)
        assert result.total == 1
        assert result.production_total == 1
        # No reason comment → must remain flagged as uncommented.
        assert len(result.uncommented_ignores) == 1
        assert result.uncommented_ignores[0].code == "arg-type"

    def test_reasoned_suppression_not_flagged(self, monkeypatch, tmp_path: Path) -> None:
        content = "x = foo()  # type: ignore[arg-type]  # reason: boundary\n"
        result = _scan_as_production(monkeypatch, tmp_path, content)
        assert result.total == 1
        assert result.uncommented_ignores == []

    def test_prose_and_real_suppression_on_adjacent_lines(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        content = (
            '"""Docs mention ``# type: ignore[arg-type]`` in prose."""\n'
            "x = foo()  # type: ignore[arg-type]\n"
        )
        result = _scan_as_production(monkeypatch, tmp_path, content)
        assert result.total == 1


# ---------------------------------------------------------------------------
# Full-scan invariants (smoke — guards the repo's Phase 1 state)
# ---------------------------------------------------------------------------


class TestScanCodebaseInvariants:
    """The real-repo scan must stay prose-free in production counts."""

    def test_repo_scan_finds_no_uncommented_production(self) -> None:
        result = scan_codebase()
        assert result.naked_ignores == []
        assert result.uncommented_ignores == []

    def test_repo_scan_production_within_baseline(self) -> None:
        # Baseline production count is 16 (baseline JSON).
        result = scan_codebase()
        assert result.production_total <= 16
