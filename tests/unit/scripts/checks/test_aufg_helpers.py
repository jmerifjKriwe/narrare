"""Tests for _aufg_helpers — AUFG markdown parsing utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from _ai_interaction_checks._aufg_helpers import (
    extract_aufg_ids,
    get_registry_ids,
    parse_aufg_registry,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_extract_aufg_ids_finds_cr_prefix() -> None:
    text = "See CR-AUFG-07-07 and CR-AUFG-07-13 for details."
    ids = extract_aufg_ids(text)
    assert ids == {"CR-AUFG-07-07", "CR-AUFG-07-13"}


def test_extract_aufg_ids_finds_bare_prefix() -> None:
    text = "AUFG-05-09 and AUFG-05-12 are resolved."
    ids = extract_aufg_ids(text)
    assert ids == {"AUFG-05-09", "AUFG-05-12"}


def test_extract_aufg_ids_finds_mixed() -> None:
    text = "CR-AUFG-07-07, AUFG-05-09, and CR-AUFG-08-01"
    ids = extract_aufg_ids(text)
    assert ids == {"CR-AUFG-07-07", "AUFG-05-09", "CR-AUFG-08-01"}


def test_extract_aufg_ids_returns_empty_for_no_match() -> None:
    assert extract_aufg_ids("No AUFG references here") == set()


def test_parse_aufg_registry_extracts_entries(tmp_path: Path) -> None:
    registry = tmp_path / "registry.md"
    registry.write_text(
        """# Registry

### CR-AUFG-07-07 — Test Entry

| Field | Value |
|-------|-------|
| Status | `open` |

**Exit evidence:** Pending.

---

### AUFG-05-09 — Resolved Entry

| Field | Value |
|-------|-------|
| Status | `resolved` |

**Exit evidence (2026-06-14):** Done. See `docs/test.md` and `scripts/check.py`.
Tests at `tests/unit/test_foo.py`.
"""
    )

    entries = parse_aufg_registry(registry)

    assert len(entries) == 2
    assert entries[0].aufg_id == "CR-AUFG-07-07"
    assert entries[0].status == "open"
    assert entries[1].aufg_id == "AUFG-05-09"
    assert entries[1].status == "resolved"
    assert "docs/test.md" in entries[1].implementation_files
    assert "scripts/check.py" in entries[1].implementation_files


def test_parse_aufg_registry_returns_empty_for_missing_file(tmp_path: Path) -> None:
    entries = parse_aufg_registry(tmp_path / "nonexistent.md")
    assert entries == []


def test_get_registry_ids_returns_set() -> None:
    from _ai_interaction_checks._aufg_helpers import AufgEntry

    entries = [
        AufgEntry(aufg_id="CR-AUFG-07-07", title="A", status="open", line_number=1),
        AufgEntry(aufg_id="CR-AUFG-07-08", title="B", status="open", line_number=10),
    ]
    ids = get_registry_ids(entries)
    assert ids == {"CR-AUFG-07-07", "CR-AUFG-07-08"}
