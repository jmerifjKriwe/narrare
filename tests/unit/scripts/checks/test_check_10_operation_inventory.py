"""Tests for Check 10 — Operation inventory gate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml
from _ai_interaction_checks.check_10_operation_inventory import (
    REQUIRED_FIELDS,
    check_operation_inventory,
    load_inventory,
)

if TYPE_CHECKING:
    from pathlib import Path


def _valid_operation(op_id: str = "test.op", status: str = "compliant") -> dict[str, Any]:
    """Return a dict with all required fields for a valid operation."""
    op: dict[str, Any] = dict.fromkeys(REQUIRED_FIELDS, "test")
    op["operation_id"] = op_id
    op["status"] = status
    return op


def _write_inventory(tmp_path: Path, operations: list[dict[str, Any]]) -> Path:
    """Write a YAML inventory file and return its path."""
    path = tmp_path / "inventory.yaml"
    data = {"version": 1, "operations": operations}
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


def test_check_operation_inventory_passes_for_valid_compliant(tmp_path: Path) -> None:
    """A fully compliant inventory with all fields passes."""
    path = _write_inventory(tmp_path, [_valid_operation()])
    passes, violations = check_operation_inventory(path)

    assert violations == []
    assert any("required" in p for p in passes)


def test_check_operation_inventory_fails_for_missing_field(tmp_path: Path) -> None:
    """An operation missing a required field is flagged."""
    op = _valid_operation()
    del op["cancel_ui"]
    path = _write_inventory(tmp_path, [op])

    _, violations = check_operation_inventory(path)

    assert any("cancel_ui" in v for v in violations)


def test_check_operation_inventory_fails_for_open_without_aufg(tmp_path: Path) -> None:
    """An open/in_progress operation without aufg_id is flagged."""
    op = _valid_operation(status="open")
    op["aufg_id"] = "n/a"
    path = _write_inventory(tmp_path, [op])

    _, violations = check_operation_inventory(path)

    assert any("requires aufg_id" in v for v in violations)


def test_check_operation_inventory_fails_for_open_with_invalid_aufg(tmp_path: Path) -> None:
    """An open operation with non-AUFG aufg_id is flagged."""
    op = _valid_operation(status="in_progress")
    op["aufg_id"] = "some-random-id"
    path = _write_inventory(tmp_path, [op])

    _, violations = check_operation_inventory(path)

    assert any("AUFG pattern" in v for v in violations)


def test_check_operation_inventory_passes_for_open_with_valid_aufg(tmp_path: Path) -> None:
    """An open operation with a valid AUFG ID passes."""
    op = _valid_operation(status="open")
    op["aufg_id"] = "CR-AUFG-07-07"
    path = _write_inventory(tmp_path, [op])

    _, violations = check_operation_inventory(path)

    assert not any("aufg_id" in v for v in violations)


def test_check_operation_inventory_fails_for_empty_operations(tmp_path: Path) -> None:
    """An inventory with no operations is flagged."""
    path = _write_inventory(tmp_path, [])

    _, violations = check_operation_inventory(path)

    assert any("no operations" in v for v in violations)


def test_check_operation_inventory_fails_for_missing_file(tmp_path: Path) -> None:
    """A missing inventory file produces a violation."""
    _, violations = check_operation_inventory(tmp_path / "nonexistent.yaml")

    assert any("not found" in v for v in violations)


def test_load_inventory_returns_dict(tmp_path: Path) -> None:
    """load_inventory returns a dict with operations key."""
    path = _write_inventory(tmp_path, [_valid_operation()])
    data = load_inventory(path)

    assert isinstance(data, dict)
    assert "operations" in data
    assert len(data["operations"]) == 1


def test_load_inventory_raises_for_missing_file(tmp_path: Path) -> None:
    """load_inventory raises FileNotFoundError for missing file."""
    try:
        load_inventory(tmp_path / "nonexistent.yaml")
        raise AssertionError("Should have raised FileNotFoundError")
    except FileNotFoundError:
        pass
