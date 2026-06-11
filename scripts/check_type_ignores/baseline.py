"""Baseline load, comparison, and update logic."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from .scanner import ROOT, ScanResult

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_BASELINE_PATH = ROOT / "scripts" / "architecture" / "type-ignore-baseline.json"


# ── Comparison dataclass ─────────────────────────────────────────────────────


@dataclass
class ComparisonResult:
    """Difference between a fresh scan and the stored baseline."""

    total_delta: int = 0  # current - baseline
    production_delta: int = 0
    naked_count: int = 0
    uncommented_count: int = 0
    new_files: list[str] = field(default_factory=list[str])
    grown_files: list[tuple[str, int, int]] = field(
        default_factory=list[tuple[str, int, int]]
    )  # (file, old, new)


# ── Baseline helpers ─────────────────────────────────────────────────────────


def load_baseline(path: Path = DEFAULT_BASELINE_PATH) -> dict[str, Any]:
    """Load a JSON baseline, returning an empty dict when absent."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        msg = f"Baseline must be a JSON object: {path}"
        raise ValueError(msg)
    return cast("dict[str, Any]", data)


def build_baseline_dict(result: ScanResult) -> dict[str, Any]:
    """Convert a ScanResult into a serializable baseline dict."""
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_count": result.total,
        "production_total": result.production_total,
        "test_total": result.test_total,
        "naked_ignores": len(result.naked_ignores),
        "uncommented_ignores": len(result.uncommented_ignores),
        "files": dict(sorted(result.by_file.items())),
    }


def compare_against_baseline(result: ScanResult, baseline: dict[str, Any]) -> ComparisonResult:
    """Return a *ComparisonResult* between a scan and a baseline dict."""
    cmp = ComparisonResult(
        total_delta=result.total - baseline.get("total_count", 0),
        production_delta=result.production_total - baseline.get("production_total", 0),
        naked_count=len(result.naked_ignores),
        uncommented_count=len(result.uncommented_ignores),
    )

    baseline_files: dict[str, int] = baseline.get("files", {}) or {}

    for file_rel, count in result.by_file.items():
        old = baseline_files.get(file_rel)
        if old is None:
            cmp.new_files.append(file_rel)
        elif count > old:
            cmp.grown_files.append((file_rel, old, count))

    return cmp
