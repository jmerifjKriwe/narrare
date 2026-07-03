"""Output formatting for test assertion audit reports.

Provides human-readable text output and machine-readable JSON output
for weak assertion findings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import FileReport, Finding, WeaknessCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _relative_path(path: Path, repo_root: Path | None = None) -> str:
    """Return a short, relative display path for a file."""
    if repo_root is None:
        repo_root = Path.cwd()
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Text report
# ---------------------------------------------------------------------------


def format_report(
    files: list[FileReport],
    threshold: float = 0.3,
    top_n: int = 30,
    repo_root: Path | None = None,
) -> str:
    """Format audit results as a human-readable text report.

    Findings are grouped by category, with each entry showing file path,
    line number, source code snippet, and fix recommendation.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    total_files = len(files)
    total_findings = sum(len(f.findings) for f in files)

    lines: list[str] = []
    lines.append("WEAK TEST ASSERTION AUDIT")
    lines.append("=" * 26)
    lines.append("")

    # Sort files by score descending, limit to top_n.
    sorted_files = sorted(files, key=lambda f: f.score, reverse=True)
    shown_files = sorted_files[:top_n]

    # Summary header.
    lines.append(
        f"Scanned: {total_files} files  |  "
        f"Total findings: {total_findings}  |  "
        f"Threshold: {threshold:.2f}  |  "
        f"Showing top {len(shown_files)} files"
    )
    lines.append("")

    # Collect all findings from shown files.
    all_findings: list[Finding] = []
    for report in shown_files:
        all_findings.extend(report.findings)

    if not all_findings:
        lines.append("No weak assertion patterns detected.  ")
        lines.append("")
        return "\n".join(lines)

    # Group by category.
    grouped: dict[WeaknessCategory, list[Finding]] = {}
    for finding in all_findings:
        grouped.setdefault(finding.category, []).append(finding)

    # Sort categories by weight (heaviest first).
    def _category_weight(cat: WeaknessCategory) -> float:
        """Get the example weight for sorting (use first finding's weight)."""
        if grouped[cat]:
            return grouped[cat][0].weight
        return 0.0

    sorted_categories = sorted(grouped, key=_category_weight, reverse=True)

    lines.append("FINDINGS BY CATEGORY")
    lines.append("-" * 20)
    lines.append("")

    for cat in sorted_categories:
        cat_findings = grouped[cat]
        cat_weight = cat_findings[0].weight
        cat_rec = cat_findings[0].recommendation

        # Category header.
        lines.append(
            f"[{cat.value}]  "
            f"(weight={cat_weight:.1f}  |  "
            f"{len(cat_findings)} occurrence{'s' if len(cat_findings) > 1 else ''})"
        )
        lines.append(f"  Fix: {cat_rec}")
        lines.append("")

        # Individual findings.
        for finding in cat_findings:
            fpath = _relative_path(finding.file_path, repo_root)
            snippet_display = finding.code_snippet if finding.code_snippet else "<empty>"
            lines.append(f"  -> {fpath}:{finding.line}  {snippet_display}")

        lines.append("")

    # Per-file score ranking.
    lines.append("TOP FILES BY WEAKNESS SCORE")
    lines.append("-" * 27)
    lines.append("")

    for report in shown_files:
        if report.score < threshold and report.total_assertions > 0:
            continue
        fpath = _relative_path(report.file_path, repo_root)
        n_findings = len(report.findings)
        bar = _score_bar(report.score)
        lines.append(
            f"  {bar}  {fpath}  "
            f"(score={report.score:.2f}, "
            f"{report.total_assertions} assertions, "
            f"{n_findings} finding{'s' if n_findings != 1 else ''})"
        )

    lines.append("")

    # Summary line.
    files_above_threshold = sum(1 for f in files if f.score >= threshold)
    lines.append(
        f"Summary: {total_files} files scanned, "
        f"{total_findings} total findings, "
        f"{files_above_threshold} files above threshold ({threshold:.2f})"
    )

    return "\n".join(lines)


def _score_bar(score: float, width: int = 10) -> str:
    """Generate a simple ASCII bar visualization of the score."""
    filled = max(0, min(width, round(score * width)))
    bar = "=" * filled + " " * (width - filled)
    return f"[{bar}]"


# ---------------------------------------------------------------------------
# Summary string
# ---------------------------------------------------------------------------


def build_summary(files: list[FileReport]) -> str:
    """Generate a Markdown summary of the audit results."""
    total_findings = sum(len(f.findings) for f in files)
    files_with_findings = sum(1 for f in files if f.findings)

    # Average score.
    avg_score = sum(f.score for f in files) / max(1, len(files))

    lines: list[str] = []
    lines.append("## Test Assertion Audit Summary\n")
    lines.append(f"- **Files scanned:** {len(files)}")
    lines.append(f"- **Files with findings:** {files_with_findings}")
    lines.append(f"- **Total findings:** {total_findings}")
    lines.append(f"- **Average file score:** {avg_score:.3f}")
    lines.append("")

    # Breakdown by category.
    category_counts: dict[str, int] = {}
    for report in files:
        for finding in report.findings:
            key = finding.category.value
            category_counts[key] = category_counts.get(key, 0) + 1

    if category_counts:
        lines.append("### Findings by Category\n")
        lines.append("| Category | Count | Weight |")
        lines.append("|----------|-------|--------|")
        weight_map = {
            "trivial_truthy": "0.6",
            "is_not_none_sole": "0.4",
            "status_code_only": "0.3",
            "assert_true_literal": "1.0",
            "response_json_truthy": "0.5",
            "pytest_raises_no_match": "0.3",
            "missing_model_validate": "0.2",
        }
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            weight = weight_map.get(cat, "?")
            lines.append(f"| {cat} | {count} | {weight} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON report
# ---------------------------------------------------------------------------


def format_json(files: list[FileReport]) -> str:
    """Format audit results as a JSON string."""
    data: list[dict[str, object]] = []
    for report in files:
        findings_list: list[dict[str, object]] = [
            {
                "category": f.category.value,
                "line": f.line,
                "code_snippet": f.code_snippet,
                "weight": f.weight,
                "recommendation": f.recommendation,
            }
            for f in report.findings
        ]
        file_data: dict[str, object] = {
            "file_path": str(report.file_path),
            "total_assertions": report.total_assertions,
            "score": round(report.score, 3),
            "findings": findings_list,
        }
        data.append(file_data)

    result: dict[str, object] = {
        "files": data,
        "total_files_scanned": len(files),
        "total_findings": sum(len(r.findings) for r in files),
    }
    return json.dumps(result, indent=2, default=str)
