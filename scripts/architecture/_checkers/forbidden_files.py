"""RULE-15 forbidden-files checker.

Extracted from ``scripts/check_architecture.py`` (RULE-06: one responsibility
per file). Enforces that no forbidden files (e.g. ``middleware.ts`` under
``packages/web``) exist in the project tree.

Next.js 16+ uses ``proxy.ts`` exclusively; the build breaks if both
``middleware.ts`` and ``proxy.ts`` are present.
"""

from __future__ import annotations

from scripts.architecture import helpers
from scripts.architecture.types import CheckResult, Violation


def check_forbidden_files(result: CheckResult) -> None:
    """RULE-15: No middleware.ts in packages/web/.

    Next.js 16+ uses proxy.ts exclusively. The build breaks if both exist.
    See: docs/_shared/CONSTRAINTS.md
    """
    forbidden_patterns = {
        "middleware.ts": "packages/web",
    }
    for filename, search_dir in forbidden_patterns.items():
        # Read ROOT lazily (helpers.ROOT) so test monkeypatching of
        # scripts.architecture.helpers.ROOT is honored — mirrors the scanner's
        # lazy-ROOT contract. Import-time binding (from helpers import ROOT)
        # would freeze the value and ignore reassignment.
        search_path = helpers.ROOT / search_dir
        if not search_path.exists():
            continue
        for match in search_path.rglob(filename):
            result.violations.append(
                Violation(
                    file=match,
                    line=0,
                    rule="RULE-15",
                    detail=(
                        f"Forbidden file '{filename}' found. "
                        f"Next.js 16+ uses proxy.ts exclusively. "
                        f"See RULE-15 in docs/_shared/CONSTRAINTS.md."
                    ),
                )
            )
