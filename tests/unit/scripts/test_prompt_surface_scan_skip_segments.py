"""Segment semantics of the A5 scan's directory skip (2026-08-19 fix).

``_run_inline_feature_prompt_scan`` (scripts/check_prompt_surface_contract.py)
excludes vendored/generated trees by whole path SEGMENT (``.venv/``,
``__pycache__/``, alembic-style ``migrations/`` directories) — never by
substring. The previous substring check (``"migrations" in str(py_file)``)
would have silently excluded any ``apps/api/**/test_migrations.py`` from
the A5 inline feature-prompt gate because its FILENAME contains
"migrations" — the sister of the scanner substring bug fixed the same day.

Non-vacuity: every probe file carries an ``agent.run(prompt=f"...")`` call
with feature framing ("Generate") — an INLINE-FEATURE-PROMPT violation via
``check_inline_feature_prompt`` (config-independent, empty baseline
ratchet). A skipped directory therefore asserts "no violation from content
that WOULD violate", and a scanned path asserts the violation actually
fires — proving the A5 scan really ran.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts.architecture.types import CheckResult
from scripts.check_prompt_surface_contract import _run_inline_feature_prompt_scan

if TYPE_CHECKING:
    from pathlib import Path

# `agent.run(prompt=f"Generate ...")` under apps/api → INLINE-FEATURE-PROMPT
# violation (config-independent probe; A5 baseline ratchet is empty).
_PROBE = (
    "async def call(agent, topic):\n"
    '    return await agent.run(prompt=f"Generate a summary for {topic}")\n'
)


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temp ROOT for both the scan driver and ``relative_to_root``.

    Without patching ``helpers.ROOT``, tmp files resolve to absolute paths
    and ``check_inline_feature_prompt``'s ``apps/api`` prefix check
    silently mis-classifies (no violations → vacuous tests). Mirrors the
    ``fake_root`` fixture pattern of
    ``tests/unit/scripts/architecture/test_scan_file_skip_segments.py``.
    """
    (tmp_path / "apps" / "api").mkdir(parents=True)
    monkeypatch.setattr("scripts.check_prompt_surface_contract.ROOT", tmp_path)
    monkeypatch.setattr("scripts.architecture.helpers.ROOT", tmp_path)
    return tmp_path


def _scan_probe(root: Path, rel_posix: str) -> CheckResult:
    """Write the A5 probe at ``rel_posix`` under root and run the A5 scan."""
    target = root / rel_posix
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_PROBE)
    result = CheckResult()
    _run_inline_feature_prompt_scan(result)
    return result


class TestSkipBySegment:
    """Whole ``migrations/``/``.venv``/``__pycache__`` segments skip."""

    def test_migrations_directory_segment_is_skipped(self, fake_root: Path) -> None:
        """A real alembic-style ``migrations/`` directory is skipped."""
        result = _scan_probe(fake_root, "apps/api/migrations/env.py")
        assert result.violations == []
        assert result.approved_exceptions == []

    def test_venv_segment_is_skipped(self, fake_root: Path) -> None:
        """A ``.venv`` path segment is skipped."""
        result = _scan_probe(fake_root, "apps/api/.venv/lib/site/foo.py")
        assert result.violations == []
        assert result.approved_exceptions == []

    def test_pycache_segment_is_skipped(self, fake_root: Path) -> None:
        """A ``__pycache__`` path segment is skipped."""
        result = _scan_probe(fake_root, "apps/api/__pycache__/foo.py")
        assert result.violations == []
        assert result.approved_exceptions == []


class TestScanDespiteSubstring:
    """Paths that merely CONTAIN the substring are scanned (regression)."""

    def test_filename_containing_migrations_is_scanned(self, fake_root: Path) -> None:
        """``apps/api/**/test_migrations.py`` enters A5 scope.

        Regression for the sister substring bug: this filename class was
        silently excluded from the A5 gate before 2026-08-19.
        """
        result = _scan_probe(fake_root, "apps/api/tests/test_migrations.py")
        assert [v.rule for v in result.violations] == ["INLINE-FEATURE-PROMPT"]

    def test_directory_name_containing_migrations_is_scanned(self, fake_root: Path) -> None:
        """``my_migrations_dir/`` is not a ``migrations`` segment → scanned."""
        result = _scan_probe(fake_root, "apps/api/my_migrations_dir/service.py")
        assert [v.rule for v in result.violations] == ["INLINE-FEATURE-PROMPT"]
