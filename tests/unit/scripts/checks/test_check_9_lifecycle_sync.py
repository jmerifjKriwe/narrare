"""Tests for Check 9 — Lifecycle sync gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from _ai_interaction_checks.check_9_lifecycle_sync import check_lifecycle_sync

if TYPE_CHECKING:
    from pathlib import Path


def test_check_lifecycle_sync_passes_when_all_ids_in_registry(tmp_path: Path) -> None:
    """Audit IDs that exist in the registry produce no violations."""
    audit = tmp_path / "audit.md"
    audit.write_text(
        """# CR-07 Audit

## Aufgaben
- **CR-AUFG-07-07:** Fix KB Field Suggest
- **CR-AUFG-07-08:** Fix KB Improve
"""
    )

    registry = tmp_path / "registry.md"
    registry.write_text(
        """# Registry

### CR-AUFG-07-07 — KB Field Suggest

| Field | Value |
|-------|-------|
| Status | `open` |

---

### CR-AUFG-07-08 — KB Improve

| Field | Value |
|-------|-------|
| Status | `open` |
"""
    )

    passes, violations = check_lifecycle_sync(audit_path=audit, registry_path=registry)

    assert violations == []
    assert any("in registry" in p for p in passes)


def test_check_lifecycle_sync_fails_for_missing_id(tmp_path: Path) -> None:
    """Audit IDs not in the registry are flagged as violations."""
    audit = tmp_path / "audit.md"
    audit.write_text("- **CR-AUFG-07-99:** Missing from registry")

    registry = tmp_path / "registry.md"
    registry.write_text("### CR-AUFG-07-07 — Exists\n\n| Status | `open` |")

    _, violations = check_lifecycle_sync(audit_path=audit, registry_path=registry)

    assert len(violations) == 1
    assert "CR-AUFG-07-99" in violations[0]


def test_check_lifecycle_sync_skips_obsolete_ids(tmp_path: Path) -> None:
    """CR-AUFG-07-01 through 07-06 are obsolete and not checked."""
    audit = tmp_path / "audit.md"
    audit.write_text(
        "- **CR-AUFG-07-01:** Obsolete (ADR-043 resolved this)\n"
        "- **CR-AUFG-07-06:** Also obsolete\n"
    )

    registry = tmp_path / "registry.md"
    registry.write_text("# Empty registry")

    passes, violations = check_lifecycle_sync(audit_path=audit, registry_path=registry)

    assert violations == []
    assert any("not applicable" in p.lower() for p in passes)


def test_check_lifecycle_sync_handles_missing_audit_file(tmp_path: Path) -> None:
    """Missing audit file produces a pass (not applicable)."""
    registry = tmp_path / "registry.md"
    registry.write_text("# Registry")

    passes, violations = check_lifecycle_sync(
        audit_path=tmp_path / "nonexistent.md",
        registry_path=registry,
    )

    assert violations == []
    assert any("not applicable" in p.lower() for p in passes)


def test_check_lifecycle_sync_accepts_covered_marker(tmp_path: Path) -> None:
    """IDs marked covered_by_existing_aufg in registry are accepted."""
    audit = tmp_path / "audit.md"
    audit.write_text("- **CR-AUFG-07-15:** New finding")

    registry = tmp_path / "registry.md"
    registry.write_text("CR-AUFG-07-15 is covered_by_existing_aufg via CR-AUFG-07-07")

    _, violations = check_lifecycle_sync(audit_path=audit, registry_path=registry)

    assert violations == []
