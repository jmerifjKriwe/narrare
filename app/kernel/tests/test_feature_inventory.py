"""The feature inventory and the roadmap agree about what the rebuild still owes.

A row marked ``backend`` names an API with no surface. That is a missing rebuild
surface, so it belongs to Phase 1 and to the roadmap section that finishes the
rebuild, not to the settled Phase 0 record.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INVENTORY = ROOT / "docs" / "features" / "INDEX.md"
ROADMAP = ROOT / "ROADMAP.md"


def _inventory_row(feature: str) -> list[str]:
    """One documented feature row, as its stripped table cells."""
    rows = [
        line
        for line in INVENTORY.read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| {feature} ")
    ]
    assert len(rows) == 1, f"expected one inventory row for {feature}, found {len(rows)}"
    return [cell.strip() for cell in rows[0].strip("|").split("|")]


def _roadmap_phase(number: str) -> str:
    """One roadmap phase section, from its heading to the next level-two heading."""
    text = ROADMAP.read_text(encoding="utf-8")
    heading = f"## Phase {number} —"
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end == -1 else text[start:end]


def test_structure_view_is_a_backend_owed_by_phase_one() -> None:
    cells = _inventory_row("Structure view (PLAN-003)")
    assert len(cells) == 4, cells
    assert cells[2] == "`backend`"
    assert cells[3] == "`1`"


def test_structure_view_is_planned_in_phase_one_not_phase_zero() -> None:
    phase_zero = _roadmap_phase("0")
    phase_one = _roadmap_phase("1")
    assert "Structure view (PLAN-003)" in phase_one
    assert "Structure view (PLAN-003)" not in phase_zero
