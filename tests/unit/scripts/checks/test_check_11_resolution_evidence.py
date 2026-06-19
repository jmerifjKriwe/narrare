"""Tests for Check 11 — Resolution evidence gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from _ai_interaction_checks._aufg_helpers import AufgEntry
from _ai_interaction_checks.check_11_resolution_evidence import (
    _has_enforcement_evidence,
    _has_implementation_files,
    _has_non_pending_evidence,
    check_resolution_evidence,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_entry(
    status: str = "resolved",
    exit_evidence_text: str = "",
    impl_files: list[str] | None = None,
) -> AufgEntry:
    return AufgEntry(
        aufg_id="CR-AUFG-07-07",
        title="Test",
        status=status,
        line_number=1,
        exit_evidence_text=exit_evidence_text,
        implementation_files=impl_files or [],
    )


def test_has_implementation_files_detects_code_paths() -> None:
    entry = _make_entry(exit_evidence_text="See scripts/check.py and test.ts")
    assert _has_implementation_files(entry)


def test_has_implementation_files_detects_md_paths() -> None:
    entry = _make_entry(exit_evidence_text="Policy at docs/policy.md")
    assert _has_implementation_files(entry)


def test_has_implementation_files_returns_false_for_empty() -> None:
    entry = _make_entry(exit_evidence_text="No files mentioned")
    assert not _has_implementation_files(entry)


def test_has_enforcement_evidence_detects_test_keyword() -> None:
    entry = _make_entry(exit_evidence_text="Tests at tests/unit/test_foo.py")
    assert _has_enforcement_evidence(entry)


def test_has_enforcement_evidence_detects_check_keyword() -> None:
    entry = _make_entry(exit_evidence_text="CI check blocks regression")
    assert _has_enforcement_evidence(entry)


def test_has_enforcement_evidence_returns_false_for_no_keywords() -> None:
    entry = _make_entry(exit_evidence_text="Just documentation here")
    assert not _has_enforcement_evidence(entry)


def test_has_non_pending_evidence_rejects_pending() -> None:
    assert not _has_non_pending_evidence(_make_entry(exit_evidence_text="Pending."))
    assert not _has_non_pending_evidence(_make_entry(exit_evidence_text=""))


def test_has_non_pending_evidence_accepts_substantive() -> None:
    assert _has_non_pending_evidence(_make_entry(exit_evidence_text="Done. See test.py"))


def test_check_resolution_evidence_passes_for_no_resolved(tmp_path: Path) -> None:
    """When no entries are resolved, check passes (not applicable)."""
    registry = tmp_path / "registry.md"
    registry.write_text("### CR-AUFG-07-07 — Open\n\n| Status | `open` |")

    passes, violations = check_resolution_evidence(registry_path=registry)

    assert violations == []
    assert any("not applicable" in p.lower() for p in passes)


def test_check_resolution_evidence_flags_resolved_without_evidence(tmp_path: Path) -> None:
    """A resolved entry with 'Pending' evidence is flagged."""
    registry = tmp_path / "registry.md"
    registry.write_text(
        """### CR-AUFG-07-07 — Test

| Status | `resolved` |

**Exit evidence:** Pending.

"""
    )

    _, violations = check_resolution_evidence(registry_path=registry)

    assert any("Pending" in v or "missing" in v for v in violations)


def test_check_resolution_evidence_passes_for_resolved_with_evidence(tmp_path: Path) -> None:
    """A resolved entry with implementation + enforcement evidence passes."""
    registry = tmp_path / "registry.md"
    registry.write_text(
        """### CR-AUFG-07-07 — Test

| Status | `resolved` |

**Exit evidence (2026-06-19):** Implemented in `scripts/check.py`.
Tests at `tests/unit/test_check.py`. CI gate blocks regression.

"""
    )

    passes, violations = check_resolution_evidence(registry_path=registry)

    assert violations == []
    assert any("evidence" in p for p in passes)
