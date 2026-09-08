"""Unit tests for the 27-entry capability registry (``benchmark.capabilities``).

Registry completeness (plan Task 7): the literal table must match the
inventory files 1:1 — the ``### CAP-...`` headings of
``benchmark/inventory/0{1,2,3}-*.md`` are parsed here via regex and
asserted for set-equality (exactly 27), per-entry direction (each
entry's own ``| Direction |`` table row), and duplicate-freeness. The
retired KB-009 merge router and the unmounted CONS-001 chapter↔KB
consistency router are inventory *findings* without CAP ids — the tests
assert they are present as ``UNAVAILABLE_SURFACES`` (with their 404
reasons) and absent from the entry table, so ``SKIPPED(unavailable)``
semantics live outside the inventory table without breaking
set-equality. Driver mapping tests pin the Task-10 completion contract:
every driven entry maps to a real driver class whose name matches the
registry ``driver_name`` (placeholder stand-ins are gone) — the plan
Task-14 driver gap (``DRIVERS_PENDING``) is closed: all 27 entries are
driven.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from benchmark.capabilities import (
    CAPABILITIES,
    UNAVAILABLE_SURFACES,
    UnknownCapabilityError,
    capability,
)
from benchmark.drivers import DRIVERS, DriverNotRegisteredError, driver_for

INVENTORY_DIR = Path(__file__).resolve().parents[1] / "inventory"
DIRECTION_FILES: tuple[tuple[str, str], ...] = (
    ("01-in.md", "in"),
    ("02-out.md", "out"),
    ("03-check.md", "check"),
)
_CAP_HEADING = re.compile(r"^### (CAP-[A-Z]+-\d+):", re.MULTILINE)
_DIRECTION_ROW = re.compile(r"\|\s*Direction\s*\|\s*(in|out|check)\s*\|")


def _inventory_entries() -> dict[str, str]:
    """Parse the inventory: cap_id -> direction, from each entry's own row."""
    entries: dict[str, str] = {}
    for filename, file_direction in DIRECTION_FILES:
        text = (INVENTORY_DIR / filename).read_text(encoding="utf-8")
        parts = _CAP_HEADING.split(text)
        heading_ids = parts[1::2]
        sections = parts[2::2]
        assert len(heading_ids) == len(sections) > 0, f"heading parse drift in {filename}"
        for cap_id, section in zip(heading_ids, sections, strict=True):
            row = _DIRECTION_ROW.search(section)
            assert row is not None, f"{cap_id}: no | Direction | row"
            assert row.group(1) == file_direction, f"{cap_id}: row disagrees with file direction"
            assert cap_id not in entries, f"{cap_id}: duplicate inventory heading"
            entries[cap_id] = row.group(1)
    return entries


# ---------------------------------------------------------------------------
# Registry completeness vs the inventory files (plan Task 7 test mandate)
# ---------------------------------------------------------------------------


def test_registry_matches_inventory_headings_set_exact_and_count_27() -> None:
    inventory = _inventory_entries()
    registry = [spec.cap_id for spec in CAPABILITIES]

    assert set(registry) == set(inventory)
    assert len(inventory) == 27
    assert len(registry) == len(set(registry)), "duplicate cap ids in the registry table"


def test_registry_directions_match_the_inventory_rows() -> None:
    inventory = _inventory_entries()

    for spec in CAPABILITIES:
        assert spec.direction == inventory[spec.cap_id]


def test_registry_shapes_and_sse_flavors_are_consistent() -> None:
    for spec in CAPABILITIES:
        assert spec.shape in ("rest", "sse", "poll")
        if spec.shape == "sse":
            assert spec.sse_flavor in ("A", "B"), f"{spec.cap_id}: SSE needs a flavor"
        else:
            assert spec.sse_flavor is None, f"{spec.cap_id}: flavor only on SSE shapes"


def test_registry_driver_names_are_nonempty_and_unique() -> None:
    names = [spec.driver_name for spec in CAPABILITIES]

    assert all(names)
    assert len(names) == len(set(names))


def test_every_registry_entry_carries_method_pinned_endpoints() -> None:
    for spec in CAPABILITIES:
        assert spec.endpoints, f"{spec.cap_id}: at least one endpoint"
        for endpoint in spec.endpoints:
            assert endpoint.method in ("GET", "POST", "PATCH", "PUT", "DELETE")
            assert endpoint.path.startswith("/")
            assert endpoint.path == endpoint.path.lower()


def test_every_registry_entry_carries_a_nonempty_output_schema_pointer() -> None:
    for spec in CAPABILITIES:
        assert spec.output_schema, f"{spec.cap_id}: output_schema must be non-empty"
        assert spec.cap_id in spec.output_schema, f"{spec.cap_id}: pointer must cite its id"
        assert len(spec.output_schema) <= 80, f"{spec.cap_id}: pointer exceeds 80 chars"


def test_mounted_registry_entries_carry_no_unavailable_reason() -> None:
    assert all(spec.unavailable_reason is None for spec in CAPABILITIES)


def test_unknown_capability_id_raises_precise_error() -> None:
    with pytest.raises(UnknownCapabilityError, match="CAP-NOPE-99"):
        capability("CAP-NOPE-99")


# ---------------------------------------------------------------------------
# The two unmounted routers — SKIPPED(unavailable) outside the 26
# ---------------------------------------------------------------------------


def test_unavailable_surfaces_are_exactly_the_two_unmounted_routers() -> None:
    assert [surface.label for surface in UNAVAILABLE_SURFACES] == [
        "KB-009 merge/dedup",
        "CONS-001 chapter-to-KB consistency",
    ]
    merge, consistency = UNAVAILABLE_SURFACES
    assert merge.direction == "in"
    assert [endpoint.path for endpoint in merge.endpoints] == ["/novels/{novel_id}/kb/merge"]
    assert consistency.direction == "check"
    assert [endpoint.path for endpoint in consistency.endpoints] == [
        "/consistency/check",
        "/consistency/check/stream",
        "/consistency/chapters/{chapter_id}/check",
    ]


def test_unavailable_reasons_name_the_404_runtime_effect() -> None:
    for surface in UNAVAILABLE_SURFACES:
        assert "404" in surface.reason, f"{surface.label}: reason must state the 404 effect"


def test_unavailable_endpoint_paths_are_absent_from_the_registry_table() -> None:
    registry_paths = {endpoint.path for spec in CAPABILITIES for endpoint in spec.endpoints}

    for surface in UNAVAILABLE_SURFACES:
        for endpoint in surface.endpoints:
            assert endpoint.path not in registry_paths


# ---------------------------------------------------------------------------
# Driver mapping — the Task-10 completion pin (every entry real, zero
# placeholders; the Task-14 CAP-IN-10 gap is closed)
# ---------------------------------------------------------------------------


def test_every_registry_id_resolves_through_driver_for() -> None:
    for spec in CAPABILITIES:
        assert driver_for(spec.cap_id) is DRIVERS[spec.cap_id]


def test_unknown_driver_id_raises_driver_not_registered() -> None:
    with pytest.raises(DriverNotRegisteredError, match="CAP-NOPE-99"):
        driver_for("CAP-NOPE-99")


def test_t10_completion_every_driven_entry_real_and_names_pinned() -> None:
    """Completion pin (plan Task 10 acceptance; Task 14 closed the gap):
    EVERY entry maps to the registry driver class — no pending ids."""
    assert set(DRIVERS) == {spec.cap_id for spec in CAPABILITIES}
    assert len(DRIVERS) == 27
    for spec in CAPABILITIES:
        driver = DRIVERS[spec.cap_id]
        assert driver.__name__ == spec.driver_name
        assert driver.__module__.startswith("benchmark.drivers.")


def test_placeholder_driver_is_gone_from_the_driver_package() -> None:
    """The completion pin is literal: no placeholder remains anywhere."""
    import benchmark.drivers as drivers_package

    assert not hasattr(drivers_package, "PlaceholderDriver")
