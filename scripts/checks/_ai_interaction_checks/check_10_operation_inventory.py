"""Check 10 — Operation inventory gate.

Validates ``scripts/checks/ai_operation_inventory.yaml`` per
ai-ux-compliance-v2 §4.  Ensures every AI operation has required fields
and every ``open``/``in_progress`` operation references an AUFG ID.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

import yaml

from ._shared import REPO_ROOT

if TYPE_CHECKING:
    from pathlib import Path

GATE = "check_10_operation_inventory"

INVENTORY_PATH = REPO_ROOT / "scripts" / "checks" / "ai_operation_inventory.yaml"

# Required fields per §4.
REQUIRED_FIELDS: list[str] = [
    "operation_id",
    "feature",
    "entry_points",
    "transport",
    "lifecycle_owner",
    "loading_feedback",
    "cancel_ui",
    "signal_propagation",
    "error_mapping",
    "partial_output",
    "ai_action_i18n",
    "deprecated_key_usage",
    "keyboard",
    "tests",
    "aufg_id",
    "exclude_entry",
    "status",
]

# Statuses that require an AUFG ID reference.
STATES_REQUIRING_AUFG: list[str] = ["open", "in_progress"]

_AUFG_PATTERN = re.compile(r"(?:CR-)?AUFG-\d{2}-\d{2,3}")


def load_inventory(path: Path | None = None) -> dict[str, Any]:
    """Load and parse the operation inventory YAML.

    Returns a dict with at least ``operations`` key.  Raises
    ``FileNotFoundError`` if the file is missing.
    """
    inventory_path = path or INVENTORY_PATH
    if not inventory_path.exists():
        raise FileNotFoundError(f"Inventory file not found: {inventory_path}")
    data = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        result: dict[str, Any] = {}
        return result
    return cast("dict[str, Any]", data)


def check_operation_inventory(
    path: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Check 10: Inventory must have required fields and AUFG links.

    Returns ``(passes, violations)``.
    """
    passes: list[str] = []
    violations: list[str] = []

    inventory_path = path or INVENTORY_PATH

    try:
        data = load_inventory(inventory_path)
    except FileNotFoundError as exc:
        violations.append(str(exc))
        return passes, violations
    except yaml.YAMLError as exc:
        violations.append(f"Inventory YAML parse error: {exc}")
        return passes, violations

    operations = data.get("operations", [])
    if not operations:
        violations.append("Inventory has no operations — expected at least the §4 minimum")
        return passes, violations

    total = len(operations)
    missing_field_count = 0
    aufg_violation_count = 0

    for op in operations:
        op_id = op.get("operation_id", "<unknown>")

        # Check required fields
        missing = [f for f in REQUIRED_FIELDS if f not in op or op[f] is None]
        if missing:
            missing_field_count += 1
            violations.append(
                f"{op_id}: missing required field(s): {', '.join(missing)}\n"
                f"  -> Add the field per §4 inventory contract"
            )

        # Check AUFG reference for open/in_progress
        status = op.get("status", "")
        if status in STATES_REQUIRING_AUFG:
            aufg_id = op.get("aufg_id", "")
            if not aufg_id or aufg_id == "n/a":
                aufg_violation_count += 1
                violations.append(
                    f"{op_id}: status '{status}' requires aufg_id reference\n"
                    f"  -> Set aufg_id to a CR-AUFG-XX-YY value"
                )
            elif not _AUFG_PATTERN.search(str(aufg_id)):
                aufg_violation_count += 1
                violations.append(
                    f"{op_id}: aufg_id '{aufg_id}' does not match AUFG pattern\n"
                    f"  -> Use format CR-AUFG-XX-YY"
                )

    if missing_field_count == 0:
        passes.append(f"All {total} operations have required §4 fields +")

    if aufg_violation_count == 0:
        open_ops = sum(1 for o in operations if o.get("status") in STATES_REQUIRING_AUFG)
        if open_ops > 0:
            passes.append(f"All {open_ops} open/in_progress operations reference AUFG IDs +")

    return passes, violations
