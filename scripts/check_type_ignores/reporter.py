"""Output formatting and reporting — human-readable and machine-readable."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .scanner import ScanResult, relative

if TYPE_CHECKING:
    from .baseline import ComparisonResult


def print_report(result: ScanResult, comparison: ComparisonResult | None) -> None:
    """Print a human-readable report to stdout."""
    # ── Summary line ──
    print(f"\n📊  Type-Ignore Scan — {result.total} total in {result.file_count} files\n")

    cat_parts: list[str] = []
    if result.production_total:
        cat_parts.append(f"{result.production_total} production")
    if result.test_total:
        cat_parts.append(f"{result.test_total} test")
    if result.other_total:
        cat_parts.append(f"{result.other_total} other")
    print(f"    Categories:  {', '.join(cat_parts)}")
    print()

    # ── Naked ignores (top-priority) ──
    if result.naked_ignores:
        print("❌  NAKED IGNORES — # type: ignore without [error-code]\n")
        for ti in result.naked_ignores:
            rel = relative(ti.file)
            print(f"    {rel}:{ti.line}  {ti.line_content}")
        print()
    else:
        print("✅  No naked # type: ignore found\n")

    # ── Uncommented production ignores ──
    if result.uncommented_ignores:
        count = len(result.uncommented_ignores)
        print(f"⚠️   {count} production suppression(s) without reason comment:\n")
        for ti in result.uncommented_ignores[:20]:  # top 20
            rel = relative(ti.file)
            print(f"    {rel}:{ti.line}  [{ti.code}]  {ti.line_content}")
        if len(result.uncommented_ignores) > 20:
            print(f"    ... and {len(result.uncommented_ignores) - 20} more")
        print()
    else:
        print("✅  All production suppressions have reason comments\n")

    # ── Top offenders ──
    print("📁  Top 15 files by suppression count:\n")
    sorted_files = sorted(result.by_file.items(), key=lambda x: -x[1])
    for file_rel, count in sorted_files[:15]:
        marker = "  "
        if comparison and comparison.new_files and file_rel in comparison.new_files:
            marker = "🆕"
        elif comparison:
            for gf, old_c, new_c in comparison.grown_files:
                if gf == file_rel:
                    marker = f"↑{new_c - old_c}"
                    break
        print(f"    {marker} {count:4d}  {file_rel}")
    print()

    # ── Comparison against baseline ──
    if comparison is not None:
        print("📈  Baseline comparison:\n")
        print(
            f"    Total:           {result.total:5d}  "
            f"(baseline: {baseline_total(comparison, result)}, "
            f"delta: {comparison.total_delta:+d})"
        )
        print(
            f"    Production:      {result.production_total:5d}  "
            f"(baseline: {baseline_production(comparison, result)}, "
            f"delta: {comparison.production_delta:+d})"
        )
        print(
            f"    Test:            {result.test_total:5d}  "
            f"(baseline: {baseline_test(comparison, result)}, "
            f"delta: {comparison.test_delta:+d})"
        )
        print(f"    Naked ignores:   {comparison.naked_count:5d}")
        print(f"    Uncommented:     {comparison.uncommented_count:5d}")
        if comparison.new_files:
            print(f"\n    🆕 New files with suppressions:  {len(comparison.new_files)}")
            for f in comparison.new_files[:10]:
                print(f"      + {f}")
            if len(comparison.new_files) > 10:
                print(f"      ... and {len(comparison.new_files) - 10} more")
        if comparison.grown_files:
            print(f"\n    📈 Files with increased count:  {len(comparison.grown_files)}")
            for f, old, new in comparison.grown_files[:10]:
                print(f"      {f}:  {old} → {new}  (+{new - old})")
            if len(comparison.grown_files) > 10:
                print(f"      ... and {len(comparison.grown_files) - 10} more")
        print()


def baseline_total(comparison: ComparisonResult, result: ScanResult) -> int:
    """Derive the baseline total count (current - delta)."""
    return result.total - comparison.total_delta


def baseline_production(comparison: ComparisonResult, result: ScanResult) -> int:
    """Derive the baseline production count."""
    return result.production_total - comparison.production_delta


def baseline_test(comparison: ComparisonResult, result: ScanResult) -> int:
    """Derive the baseline test count."""
    return result.test_total - comparison.test_delta


def build_json_output(result: ScanResult, comparison: ComparisonResult | None) -> dict[str, Any]:
    """Build a machine-readable JSON dict for CI consumption."""
    out: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_count": result.total,
        "production_total": result.production_total,
        "test_total": result.test_total,
        "other_total": result.other_total,
        "naked_ignores": len(result.naked_ignores),
        "uncommented_ignores": len(result.uncommented_ignores),
        "files": result.by_file,
    }

    if comparison is not None:
        out["baseline"] = {
            "total_delta": comparison.total_delta,
            "production_delta": comparison.production_delta,
            "new_files": comparison.new_files,
            "grown_files": [(f, old, new) for f, old, new in comparison.grown_files],
        }

    return out
