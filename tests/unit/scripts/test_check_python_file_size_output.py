"""Tests for scripts/check_python_file_size.py — output and baseline functions.

Covers format_report, format_json, update_baseline, and display_path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_python_file_size import (  # noqa: E402
    FileSizeViolation,
    _display_path,
    format_json,
    format_report,
    update_baseline,
)

# ---------------------------------------------------------------------------
# Tests: format_report
# ---------------------------------------------------------------------------


class TestFormatReport:
    """Human-readable report formatting."""

    def test_no_violations(self) -> None:
        report = format_report([])
        assert "✅ All Python files are within hard limits" in report

    def test_violations_shown(self) -> None:
        violations = [
            FileSizeViolation(path=Path("apps/service.py"), lines=350, limit=300, kind="service"),
        ]
        report = format_report(violations)
        assert "WARN: apps/service.py has 350 lines" in report
        assert "service hard limit: 300" in report

    def test_sorted_by_lines_descending(self) -> None:
        violations = [
            FileSizeViolation(path=Path("a.py"), lines=410, limit=400, kind="general"),
            FileSizeViolation(path=Path("b.py"), lines=500, limit=400, kind="general"),
        ]
        report = format_report(violations)
        # b.py (500 lines) should appear before a.py (410 lines)
        pos_b = report.index("b.py")
        pos_a = report.index("a.py")
        assert pos_b < pos_a


# ---------------------------------------------------------------------------
# Tests: format_json
# ---------------------------------------------------------------------------


class TestFormatJson:
    """Machine-readable JSON output."""

    def test_json_structure(self) -> None:
        violations = [
            FileSizeViolation(path=Path("apps/service.py"), lines=350, limit=300, kind="service"),
        ]
        data = json.loads(format_json(violations))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["path"] == "apps/service.py"
        assert data[0]["lines"] == 350
        assert data[0]["limit"] == 300
        assert data[0]["kind"] == "service"
        assert "fingerprint" in data[0]

    def test_empty_violations(self) -> None:
        data = json.loads(format_json([]))
        assert data == []


# ---------------------------------------------------------------------------
# Tests: update_baseline
# ---------------------------------------------------------------------------


class TestUpdateBaseline:
    """Baseline write functionality."""

    def test_creates_new_baseline(self, tmp_path: Path) -> None:
        baseline_path = tmp_path / "baseline.json"
        violations = [
            FileSizeViolation(path=Path("apps/service.py"), lines=350, limit=300, kind="service"),
        ]
        update_baseline(violations, baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert "python_file_size_violations" in data
        fps = data["python_file_size_violations"]
        assert len(fps) == 1
        assert "apps/service.py" in fps[0]

    def test_preserves_existing_sections(self, tmp_path: Path) -> None:
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps({"existing_section": ["item1"]}),
            encoding="utf-8",
        )

        update_baseline([], baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert data["existing_section"] == ["item1"]
        assert data["python_file_size_violations"] == []

    def test_overwrites_python_section(self, tmp_path: Path) -> None:
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps({"python_file_size_violations": ["old"]}),
            encoding="utf-8",
        )

        violations = [
            FileSizeViolation(path=Path("new.py"), lines=450, limit=400, kind="general"),
        ]
        update_baseline(violations, baseline_path)

        data = json.loads(baseline_path.read_text(encoding="utf-8"))
        fps = data["python_file_size_violations"]
        assert len(fps) == 1
        assert "new.py" in fps[0]

    def test_preserves_non_ascii_in_other_sections_byte_identically(self, tmp_path: Path) -> None:
        """2026-08-19 fix (found during gate unification): the shared
        ai-gate-baseline.json carries non-ASCII text (em-dashes) in other
        sections; update_baseline must not escape it — that churned every
        unrelated line on each baseline update."""
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps(
                {"approved_exceptions": ["pyproject | RULE-01b | x.py — reason"]},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        update_baseline([], baseline_path)

        content = baseline_path.read_text(encoding="utf-8")
        assert "\\u2014" not in content, "non-ASCII must stay literal, not \\u-escaped"
        assert "x.py — reason" in content


# ---------------------------------------------------------------------------
# Tests: _display_path
# ---------------------------------------------------------------------------


class TestDisplayPath:
    """Path display formatting."""

    def test_relative_to_root(self, tmp_path: Path) -> None:
        path = tmp_path / "apps" / "service.py"
        result = _display_path(path, tmp_path)
        assert result == Path("apps/service.py")

    def test_outside_root_returns_posix(self) -> None:
        path = Path("/tmp/some/other/file.py")
        result = _display_path(path, Path("/home/user/project"))
        assert result == Path("/tmp/some/other/file.py")
