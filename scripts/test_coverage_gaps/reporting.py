"""Output formatting for test coverage gap reports.

Provides human-readable text output and machine-readable JSON output
for test coverage gap analysis results.

See: docs/_shared/CONSTRAINTS.md (RULE-10)
"""

from __future__ import annotations

import json

from .discovery import REPO_ROOT, SourceFile


def format_report(results: list[SourceFile]) -> str:
    """Format a human-readable test existence report."""
    lines: list[str] = []
    lines.append("TEST EXISTENCE REPORT")
    lines.append("=" * 21)
    lines.append("")

    ok_count = 0
    low_count = 0
    missing_count = 0

    for source in results:
        if source.status == "ok":
            ok_count += 1
            lines.append(
                f"  {source.display_path}"
                f" -> {source.test_display_paths}"
                f" ({source.public_methods} methods, "
                f"{source.test_functions} tests)"
            )
        elif source.status == "low":
            low_count += 1
            lines.append(
                f"  {source.display_path}"
                f" -> {source.test_display_paths}"
                f" ({source.public_methods} methods, "
                f"{source.test_functions} tests)"
                f" - LOW COVERAGE"
            )
        else:
            missing_count += 1
            lines.append(f"  {source.display_path} -> NO TEST FILE FOUND")

    lines.append("")
    total = len(results)
    lines.append(
        f"Summary: {total} services checked, "
        f"{missing_count} missing test files, "
        f"{low_count} low coverage"
    )

    return "\n".join(lines)


def format_json(results: list[SourceFile]) -> str:
    """Format results as JSON."""
    data: list[dict[str, object]] = []
    for source in results:
        data.append(
            {
                "source": source.display_path,
                "domain": source.domain,
                "layer": source.layer,
                "public_methods": source.public_methods,
                "test_files": [
                    t.relative_to(REPO_ROOT).as_posix() if t.exists() else str(t)
                    for t in source.test_files
                ]
                if source.test_files
                else [],
                "test_functions": source.test_functions,
                "coverage_ratio": round(source.coverage_ratio, 2),
                "status": source.status,
            }
        )
    return json.dumps(data, indent=2)
