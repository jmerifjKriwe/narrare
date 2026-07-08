"""
Type-Ignore Discipline Checker (RULE-23).

Enforces type-ignore suppression discipline across the Narrare codebase:

1. Naked ``# type: ignore`` (without ``[error-code]``) — always an error.
2. Production-code suppressions (``apps/api/narrare/``,
   ``packages/core/narrare_core/``) require a reason comment.
3. Total / production-suppression counts must not exceed the stored baseline.

Exit codes
----------
0 — All checks pass.
1 — Warnings: total suppression count exceeds baseline.
2 — Errors: naked ignores, production total exceeds baseline, or
    uncommented production ignores found.

Usage
-----
::

    # Basic check (uses default baseline)
    python -m scripts.check_type_ignores

    # Custom baseline path
    python -m scripts.check_type_ignores --baseline path/to/baseline.json

    # Update (create / overwrite) the baseline from current state
    python -m scripts.check_type_ignores --update

    # Update to a specific path
    python -m scripts.check_type_ignores --update --baseline path/to/baseline.json

Importable
----------
    >>> from scripts.check_type_ignores import check_type_ignores
    >>> result = check_type_ignores()           # dict with scan + comparison
    >>> result = check_type_ignores("my.json")  # explicit baseline path
"""

from __future__ import annotations

from .main import check_type_ignores

__all__ = ["check_type_ignores"]
