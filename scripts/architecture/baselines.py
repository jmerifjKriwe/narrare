"""Machine-readable baseline helpers for ratcheted architecture gates.

Baselines intentionally allow existing debt to shrink without churn, but they
make new debt explicit: a current item that is not listed in the baseline is a
gate violation until the debt is fixed or an ADR-approved baseline update lands.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BASELINE_PATH = ROOT / "scripts" / "architecture" / "ai-gate-baseline.json"


@dataclass(frozen=True)
class BaselineComparison:
    """Comparison between current findings and a stored baseline section."""

    section: str
    current: set[str]
    baseline: set[str]
    new_items: set[str] = field(init=False)
    resolved_items: set[str] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "new_items", self.current - self.baseline)
        object.__setattr__(self, "resolved_items", self.baseline - self.current)

    @property
    def ok(self) -> bool:
        """Return True when no finding grew beyond the stored baseline."""
        return not self.new_items


def load_baseline(path: Path = DEFAULT_BASELINE_PATH) -> dict[str, Any]:
    """Load a JSON baseline file, returning an empty baseline if absent."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data: Any = json.load(fh)
    if not isinstance(data, dict):
        msg = f"Baseline must be a JSON object: {path}"
        raise ValueError(msg)
    return cast("dict[str, Any]", data)


def section_items(
    baseline: dict[str, Any],
    section: str,
) -> set[str]:
    """Read one string-list section from a loaded baseline."""
    raw: Any = baseline.get(section, [])
    if raw is None:
        return set()
    if not isinstance(raw, list):
        msg = f"Baseline section '{section}' must be a list of strings"
        raise ValueError(msg)
    items = cast("list[object]", raw)
    if not all(isinstance(item, str) for item in items):
        msg = f"Baseline section '{section}' must be a list of strings"
        raise ValueError(msg)
    return {cast("str", item) for item in items}


def compare_section(
    current: set[str],
    section: str,
    path: Path = DEFAULT_BASELINE_PATH,
) -> BaselineComparison:
    """Compare current findings against one baseline section."""
    baseline = load_baseline(path)
    return BaselineComparison(
        section=section,
        current=current,
        baseline=section_items(baseline, section),
    )


def stable_fingerprint(*parts: object) -> str:
    """Build a reviewable, deterministic finding fingerprint."""
    return " | ".join(str(part).strip() for part in parts)


def format_comparison(comparison: BaselineComparison, label: str) -> str:
    """Format a concise ratchet report for CLI output."""
    lines = [
        f"{label}: {len(comparison.current)} current, "
        f"{len(comparison.baseline)} baseline, "
        f"{len(comparison.new_items)} new, "
        f"{len(comparison.resolved_items)} resolved",
    ]
    for item in sorted(comparison.new_items):
        lines.append(f"NEW: {item}")
    for item in sorted(comparison.resolved_items):
        lines.append(f"RESOLVED: {item}")
    return "\n".join(lines)
