"""RULE-04 · File size limits (shared SSOT classification)."""

from __future__ import annotations

from pathlib import Path

from scripts.architecture.file_size_limits import FileSizeLimitsError, classify
from scripts.architecture.types import Violation


def check_file_size(
    rel_path: str,
    source_lines: list[str],
    limits: dict[str, int],
) -> list[Violation]:
    """Hard file size limits by file category.

    Classification and limits come from the shared RULE-04 SSOT
    (``scripts/architecture/file_size_limits.py``) — the same module
    ``scripts/check_python_file_size.py`` consumes, so both gates classify
    identically by construction (priority: ``test_*`` first, then the
    path-based ``scripts/`` rule, then the name-based categories).

    An empty ``limits`` mapping means "no override" (the validated pyproject
    SSOT table applies); a partial or stale table is reported as a RULE-04
    violation instead of silently falling back to hardcoded defaults
    (RULE-11 — per-key fallbacks are how the two gates drifted apart).
    """
    line_count = len(source_lines)

    try:
        _, limit = classify(rel_path, limits if limits else None)
    except FileSizeLimitsError as exc:
        return [
            Violation(
                file=Path(rel_path),
                line=line_count,
                rule="RULE-04",
                detail=f"Invalid file_size_limits table: {exc}",
            )
        ]

    if line_count > limit:
        return [
            Violation(
                file=Path(rel_path),
                line=line_count,
                rule="RULE-04",
                detail=f"File has {line_count} lines (hard limit: {limit}). Split required.",
            )
        ]
    return []
