"""Baseline load, comparison, and update logic."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from .scanner import ROOT, ScanResult

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

DEFAULT_BASELINE_PATH = ROOT / "scripts" / "architecture" / "type-ignore-baseline.json"


# ── Comparison dataclass ─────────────────────────────────────────────────────


@dataclass
class ComparisonResult:
    """Difference between a fresh scan and the stored baseline."""

    total_delta: int = 0  # current - baseline
    production_delta: int = 0
    test_delta: int = 0
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


class BaselineShrinkError(RuntimeError):
    """Raised when a baseline update would remove tracked file keys.

    A disappearing ``files`` key means a file's suppressions dropped to
    zero (or the file was deleted) — a ratchet event that must be named
    deliberately via ``allow_removed`` / ``--allow-removed <file,...>`` so
    every baseline drop is auditable. Mirrors the explicit-removal
    discipline of ``scripts/_coverage_model.py`` (73bff8c2). Also raised
    when ``allow_removed`` names keys that are not actually disappearing:
    the allowance is an assertion about reality and must match it exactly.
    """


def save_baseline(
    result: ScanResult,
    path: Path = DEFAULT_BASELINE_PATH,
    *,
    allow_removed: Collection[str] = (),
) -> bool:
    """Persist *result* as the baseline at *path* (guarded update).

    Removals of ``files`` keys are refused unless the removed key set
    matches *allow_removed* exactly — see :class:`BaselineShrinkError`.
    A value-identical update is a byte-level no-op (the file, including
    its ``generated_at`` timestamp, is left untouched) so re-running
    ``--update-baseline`` against an unchanged tree cannot drift.

    Returns ``True`` when the file was written, ``False`` on no-op.
    """
    new = build_baseline_dict(result)
    existing = load_baseline(path)

    existing_files: set[str] = set(existing.get("files", {}) or {})
    new_files = set(new["files"])
    removed = existing_files - new_files
    allowed = set(allow_removed)

    if removed != allowed:
        details: list[str] = []
        unapproved = sorted(removed - allowed)
        overstated = sorted(allowed - removed)
        if unapproved:
            details.append(
                "removed without approval: "
                + ", ".join(unapproved[:10])
                + (f" (+{len(unapproved) - 10} more)" if len(unapproved) > 10 else "")
            )
        if overstated:
            details.append(
                "named in allow_removed but not actually removed: "
                + ", ".join(overstated[:10])
                + (f" (+{len(overstated) - 10} more)" if len(overstated) > 10 else "")
            )
        raise BaselineShrinkError(
            "Refusing to update the type-ignore baseline ("
            + "; ".join(details)
            + "). A disappearing files-key means the file's suppressions "
            "dropped to zero (or the file was deleted) — if that is "
            "deliberate, name the keys exactly via "
            "--allow-removed <file,...>."
        )

    payload_keys = (
        "total_count",
        "production_total",
        "test_total",
        "naked_ignores",
        "uncommented_ignores",
        "files",
    )
    if existing and all(existing.get(k) == new[k] for k in payload_keys):
        # Nothing changed — do not rewrite (keeps ``generated_at`` stable
        # and avoids commit noise for a semantically unchanged baseline).
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(new, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return True


def compare_against_baseline(result: ScanResult, baseline: dict[str, Any]) -> ComparisonResult:
    """Return a *ComparisonResult* between a scan and a baseline dict."""
    cmp = ComparisonResult(
        total_delta=result.total - baseline.get("total_count", 0),
        production_delta=result.production_total - baseline.get("production_total", 0),
        test_delta=result.test_total - baseline.get("test_total", 0),
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
