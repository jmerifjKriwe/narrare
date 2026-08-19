"""Segment semantics of ``scan_file``'s directory skip (2026-08-19 fix).

``scan_file`` excludes vendored/generated trees by whole path SEGMENT
(``.venv/``, ``node_modules/``, alembic-style ``migrations/``
directories) — never by substring. The previous substring check
(``"migrations" in rel_path``) silently excluded
``tests/integration/adaptive/test_migrations.py`` and
``tests/integration/analysis/test_author_voice_migrations.py`` from
every AST checker because their FILENAMES contain "migrations".

Non-vacuity: every probe file carries a bare ``except:`` (RULE-11 via
``check_bare_except`` — a config-independent violation). A skipped
directory therefore asserts "no violation from content that WOULD
violate", and a scanned path asserts the violation actually fires —
proving the AST scan really ran.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts.architecture._checkers import scan_file
from scripts.architecture.file_size_limits import CATEGORY_ORDER
from scripts.architecture.types import CheckResult

if TYPE_CHECKING:
    from pathlib import Path

# Bare `except:` → RULE-11 violation (config-independent probe).
_PROBE = "try:\n    x = 1\nexcept:\n    pass\n"

# Complete file_size_limits table (all canonical categories, uniform
# limit) — required because an empty table makes check_file_size fall
# back to the pyproject SSOT load, which fails (RULE-04 "invalid table")
# under the monkeypatched fake ROOT below.
_VALID_LIMITS: dict[str, int] = dict.fromkeys(CATEGORY_ORDER, 400)


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temp ROOT so ``relative_to_root`` yields repo-style relative paths.

    Mirrors the ``scan_dir`` fixture in
    ``tests/unit/scripts/test_architecture_incremental.py``: without the
    patch, tmp files resolve to absolute paths and path-prefix checkers
    silently mis-classify.
    """
    (tmp_path / "pyproject.toml").write_text("[tool.narrare.architecture]\n")
    monkeypatch.setattr("scripts.architecture.helpers.ROOT", tmp_path)
    return tmp_path


def _scan_probe(root: Path, rel_posix: str) -> CheckResult:
    """Write the RULE-11 probe at ``rel_posix`` under root and scan it."""
    target = root / rel_posix
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_PROBE)
    result = CheckResult()
    scan_file(target, {"file_size_limits": _VALID_LIMITS}, result)
    return result


class TestSkipBySegment:
    """Whole ``migrations/``/``.venv``/``node_modules`` segments skip."""

    def test_migrations_directory_segment_is_skipped(self, fake_root: Path) -> None:
        """A real alembic-style ``migrations/`` directory is skipped."""
        result = _scan_probe(fake_root, "apps/api/migrations/env.py")
        assert result.files_checked == 0
        assert result.violations == []

    def test_venv_segment_is_skipped(self, fake_root: Path) -> None:
        """A ``.venv`` path segment is skipped."""
        result = _scan_probe(fake_root, ".venv/lib/site/foo.py")
        assert result.files_checked == 0
        assert result.violations == []

    def test_node_modules_segment_is_skipped(self, fake_root: Path) -> None:
        """A ``node_modules`` path segment is skipped."""
        result = _scan_probe(fake_root, "packages/web/node_modules/pkg/foo.py")
        assert result.files_checked == 0
        assert result.violations == []


class TestScanDespiteSubstring:
    """Paths that merely CONTAIN the substring are scanned (regression)."""

    def test_filename_containing_migrations_is_scanned(self, fake_root: Path) -> None:
        """``tests/integration/adaptive/test_migrations.py`` enters AST scope.

        Regression for the substring bug: this exact filename was
        silently excluded from every AST checker before 2026-08-19.
        """
        result = _scan_probe(fake_root, "tests/integration/adaptive/test_migrations.py")
        assert result.files_checked == 1
        assert [v.rule for v in result.violations] == ["RULE-11"]

    def test_author_voice_migrations_filename_is_scanned(self, fake_root: Path) -> None:
        """``tests/integration/analysis/test_author_voice_migrations.py`` is scanned."""
        result = _scan_probe(
            fake_root, "tests/integration/analysis/test_author_voice_migrations.py"
        )
        assert result.files_checked == 1
        assert [v.rule for v in result.violations] == ["RULE-11"]

    def test_directory_name_containing_migrations_is_scanned(self, fake_root: Path) -> None:
        """``my_migrations_dir/`` is not a ``migrations`` segment → scanned."""
        result = _scan_probe(fake_root, "tests/unit/my_migrations_dir/test_x.py")
        assert result.files_checked == 1
        assert [v.rule for v in result.violations] == ["RULE-11"]
