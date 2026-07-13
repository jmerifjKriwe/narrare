"""Tests for scripts/check_empty_kb_vars.py — ratcheted empty KB var gate.

Covers detection (regex matching), exclusion rules (_should_skip), collection
(collect_empty_kb_vars), and the baseline ratchet gate (main exit codes).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.check_empty_kb_vars import (  # noqa: E402
    _should_skip,
    collect_empty_kb_vars,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_py_file(root: Path, rel: str, content: str) -> Path:
    """Create a .py file at the relative path under root."""
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Tests: _should_skip
# ---------------------------------------------------------------------------


class TestShouldSkip:
    """File exclusion logic for test files, pycache, and migrations."""

    def test_test_prefix_skipped(self) -> None:
        assert _should_skip(Path("test_service.py"))

    def test_test_suffix_skipped(self) -> None:
        assert _should_skip(Path("service_test.py"))

    def test_test_helpers_skipped(self) -> None:
        assert _should_skip(Path("service_test_helpers.py"))

    def test_regular_file_not_skipped(self) -> None:
        assert not _should_skip(Path("service.py"))

    def test_pycache_skipped(self) -> None:
        assert _should_skip(Path("apps") / "__pycache__" / "module.py")

    def test_alembic_versions_skipped(self) -> None:
        assert _should_skip(Path("alembic") / "versions" / "0001_initial.py")


# ---------------------------------------------------------------------------
# Tests: detection
# ---------------------------------------------------------------------------


class TestDetection:
    """The checker detects empty KB variable assignments."""

    def test_finds_empty_kb_var_assignment(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/service.py",
            'context = {\n    "kb_characters": ""\n}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert "apps/api/narrare/analysis/service.py | kb_characters" in findings

    def test_ignores_non_empty_assignment(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/service.py",
            'context = {\n    "kb_characters": "Alice, Bob"\n}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert findings == set()

    def test_finds_all_four_kb_vars(self, tmp_path: Path) -> None:
        content = (
            "ctx = {\n"
            '    "kb_characters": "",\n'
            '    "kb_locations": "",\n'
            '    "kb_factions": "",\n'
            '    "kb_relationships": "",\n'
            "}\n"
        )
        _make_py_file(tmp_path, "apps/api/narrare/analysis/service.py", content)
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert len(findings) == 4

    def test_finds_same_var_in_multiple_files(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/a.py",
            'x = {"kb_characters": ""}\n',
        )
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/b.py",
            'y = {"kb_characters": ""}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert len(findings) == 2

    def test_handles_whitespace_around_colon(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/service.py",
            'x = {"kb_characters"   :   ""}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# Tests: exclusion
# ---------------------------------------------------------------------------


class TestExclusion:
    """The checker excludes test files and other non-production code."""

    def test_excludes_test_prefix_files(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/test_service.py",
            'x = {"kb_characters": ""}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert findings == set()

    def test_excludes_test_helpers(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/service_test_helpers.py",
            'x = {"kb_characters": ""}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert findings == set()

    def test_excludes_test_suffix_files(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/service_test.py",
            'x = {"kb_characters": ""}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert findings == set()

    def test_excludes_pycache(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/__pycache__/module.py",
            'x = {"kb_characters": ""}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert findings == set()

    def test_excludes_alembic_versions(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/alembic/versions/0001_initial.py",
            'x = {"kb_characters": ""}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert findings == set()

    def test_production_file_still_detected(self, tmp_path: Path) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/voice_check_prompt.py",
            'x = {"kb_characters": ""}\n',
        )
        findings = collect_empty_kb_vars(
            scan_root=tmp_path / "apps" / "api" / "narrare",
            repo_root=tmp_path,
        )
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# Tests: baseline gate (main exit codes)
# ---------------------------------------------------------------------------


class TestMainGate:
    """The checker exits 0 on matching baseline, 1 on new findings."""

    @pytest.fixture
    def scan_root(self, tmp_path: Path) -> Path:
        """Create a scan root mirroring production layout under tmp_path."""
        root = tmp_path / "apps" / "api" / "narrare"
        root.mkdir(parents=True)
        return root

    def test_exits_zero_when_findings_match_baseline(
        self,
        tmp_path: Path,
        scan_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/svc.py",
            'x = {"kb_characters": ""}\n',
        )
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps({"empty_kb_vars": ["apps/api/narrare/analysis/svc.py | kb_characters"]})
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_empty_kb_vars.py",
                "--baseline",
                str(baseline_path),
                "--scan-root",
                str(scan_root),
                "--repo-root",
                str(tmp_path),
            ],
        )
        from scripts.check_empty_kb_vars import main

        assert main() == 0

    def test_exits_one_on_new_finding(
        self,
        tmp_path: Path,
        scan_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _make_py_file(
            tmp_path,
            "apps/api/narrare/analysis/svc.py",
            'x = {"kb_characters": ""}\n',
        )
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(json.dumps({"empty_kb_vars": []}))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_empty_kb_vars.py",
                "--baseline",
                str(baseline_path),
                "--scan-root",
                str(scan_root),
                "--repo-root",
                str(tmp_path),
            ],
        )
        from scripts.check_empty_kb_vars import main

        assert main() == 1
        captured = capsys.readouterr()
        assert "NEW:" in captured.out
        assert "kb_characters" in captured.out

    def test_reports_resolved_when_baseline_item_disappears(
        self,
        tmp_path: Path,
        scan_root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # No actual findings — the file doesn't exist
        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(
            json.dumps({"empty_kb_vars": ["apps/api/narrare/analysis/gone.py | kb_characters"]})
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_empty_kb_vars.py",
                "--baseline",
                str(baseline_path),
                "--scan-root",
                str(scan_root),
                "--repo-root",
                str(tmp_path),
            ],
        )
        from scripts.check_empty_kb_vars import main

        assert main() == 0
        captured = capsys.readouterr()
        assert "RESOLVED:" in captured.out
        assert "0 current" in captured.out
