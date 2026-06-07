"""Doc-drift detection for Narrare documentation governance.

Validates cross-references between ADRs, specs, RULE-XX constraints,
and checker terminology. Extends check_doc_drift.py with governance checks
per ADR-041 Decision 2.

Check families:
    - ADR cross-reference and status consistency
    - Spec/RULE-XX reference alignment
    - Checker terminology alignment with canonical sources
"""

from __future__ import annotations

from pathlib import Path


def safe_relative(
    path: Path,
    *,
    repo_root: Path | None = None,
) -> str:
    """Return path relative to repo_root, falling back to str(path).

    Handles tmp_path scenarios in tests where the path is outside the repo.
    """
    root = repo_root or Path(__file__).resolve().parent.parent.parent
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
