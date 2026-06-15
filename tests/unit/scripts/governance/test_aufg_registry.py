"""Tests for the AUFG registry parser (ADR-047 Phase 2)."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from governance.aufg_registry import (  # noqa: E402
    AufgEntry,
    load_registry,
    parse_registry,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_REGISTRY = """\
# AUFG Registry

## Active AUFGs

### AUFG-05-07 — CORS-/Rate-Limiting-Security-Audit

| Field | Value |
|-------|-------|
| ID | AUFG-05-07 |
| Title | CORS-/Rate-Limiting-Security-Audit |
| Status | `resolved` |

Some acceptance criteria text.

### AUFG-05-12 — Rate-Limiting fuer AI-Endpoints

| Field | Value |
|-------|-------|
| ID | AUFG-05-12 |
| Status | `open` |

Acceptance criteria.

## Coverage Pointers

### AUFG-05-03 — Memory/Embedding-Spans

| Field | Value |
|-------|-------|
| ID | AUFG-05-03 |
| Status | `covered_by_existing_aufg` |

## Accepted Enhancements

### AE-05-01 — Cosign/SLSA Hardening

| Field | Value |
|-------|-------|
| ID | AE-05-01 |
| Status | `accepted_enhancement` |

## Accepted Risks

### AR-05-02 — Rate-Limiting Backend Discrepancy

| Field | Value |
|-------|-------|
| ID | AR-05-02 |
| Type | `accepted_risk` |
"""


# ---------------------------------------------------------------------------
# parse_registry
# ---------------------------------------------------------------------------


def test_parse_registry_extracts_aufg_entries() -> None:
    """AUFG entries under 'Active AUFGs' are parsed with correct IDs."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    assert registry.has("AUFG-05-07")
    assert registry.has("AUFG-05-12")
    assert registry.has("AUFG-05-03")


def test_parse_registry_extracts_accepted_risk_entry() -> None:
    """AR-* entries are parsed from the 'Accepted Risks' section."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    assert registry.has("AR-05-02")
    entry = registry.get("AR-05-02")
    assert entry is not None
    assert entry.status == "accepted_risk"


def test_parse_registry_extracts_accepted_enhancement_entry() -> None:
    """AE-* entries are parsed from the 'Accepted Enhancements' section."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    assert registry.has("AE-05-01")
    entry = registry.get("AE-05-01")
    assert entry is not None
    assert entry.status == "accepted_enhancement"


def test_parse_registry_strips_backticks_from_status() -> None:
    """Backtick-wrapped status values like `` `resolved` `` are normalised."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    entry = registry.get("AUFG-05-07")
    assert entry is not None
    assert entry.status == "resolved"
    assert "`" not in entry.status


def test_parse_registry_extracts_title_from_header() -> None:
    """The title after the em-dash separator is captured."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    entry = registry.get("AUFG-05-07")
    assert entry is not None
    assert "CORS" in entry.title


def test_parse_registry_preserves_open_status() -> None:
    """Non-resolved statuses are captured accurately."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    entry = registry.get("AUFG-05-12")
    assert entry is not None
    assert entry.status == "open"


def test_parse_registry_empty_text_returns_empty_registry() -> None:
    """An empty or whitespace-only document produces zero entries."""
    registry = parse_registry("")

    assert len(registry.entries) == 0


def test_parse_registry_no_entries_returns_empty() -> None:
    """A document without entry headers produces zero entries."""
    registry = parse_registry("# Some doc\n\nJust prose, no entries.\n")

    assert len(registry.entries) == 0


def test_parse_registry_entry_id_is_well_formed() -> None:
    """Each entry ID follows the PREFIX-NN-NN pattern."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    for entry_id in registry.entries:
        assert "-" in entry_id
        parts = entry_id.split("-")
        assert len(parts) == 3
        assert parts[0] in ("AUFG", "AR", "AE")


# ---------------------------------------------------------------------------
# Registry lookup
# ---------------------------------------------------------------------------


def test_registry_get_returns_none_for_missing_id() -> None:
    """Lookup of a non-existent ID returns None, not an error."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    assert registry.get("AUFG-99-99") is None


def test_registry_has_returns_false_for_missing_id() -> None:
    """has() returns False for IDs not in the registry."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    assert not registry.has("AUFG-99-99")


def test_registry_entries_is_a_dict_of_aufg_entry() -> None:
    """Every value in entries is an AufgEntry dataclass."""
    registry = parse_registry(_SAMPLE_REGISTRY)

    for entry in registry.entries.values():
        assert isinstance(entry, AufgEntry)
        assert entry.entry_id
        assert entry.title
        assert entry.status


# ---------------------------------------------------------------------------
# load_registry
# ---------------------------------------------------------------------------


def test_load_registry_reads_file_from_disk(tmp_path: Path) -> None:
    """load_registry reads a markdown file and parses it."""
    registry_file = tmp_path / "aufg-registry.md"
    registry_file.write_text(_SAMPLE_REGISTRY, encoding="utf-8")

    registry = load_registry(registry_file)

    assert registry.has("AUFG-05-07")
    assert registry.has("AR-05-02")


# ---------------------------------------------------------------------------
# Real registry smoke test
# ---------------------------------------------------------------------------


def test_parse_real_aufg_registry_has_expected_entries() -> None:
    """The real aufg-registry.md parses without error and has known entries."""
    real_path = _PROJECT_ROOT / "docs" / "architecture" / "governance" / "aufg-registry.md"
    if not real_path.exists():
        return  # pragma: no cover — repo layout may differ in CI sandbox

    registry = load_registry(real_path)

    # Known entries from the seeded registry
    assert registry.has("AUFG-05-07")
    assert registry.has("AUFG-05-09")
    assert registry.has("AR-05-02")
    assert registry.has("AE-05-01")
