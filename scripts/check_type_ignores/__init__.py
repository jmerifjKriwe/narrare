"""
Type-Ignore Discipline Checker (RULE-23).

Enforces type-ignore suppression discipline across the Narrare codebase:

1. Naked ``# type: ignore`` (without ``[error-code]``) — always an error.
2. Production-code suppressions (``apps/api/narrare/``,
   ``packages/core/narrare_core/``) require a reason comment.
3. Total / production / test-suppression counts must not exceed the stored
   baseline (ratchet-down; production delta must stay ≤ 0).

Exit codes
----------
0 — All checks pass.
1 — Budget growth: total or test suppression count exceeds the frozen
    baseline (ratchet; blocking in CI — any non-zero exit fails the step).
2 — Errors: naked ignores, production total exceeds baseline, or
    uncommented production ignores found.

Usage
-----
::

    # Basic check (uses default baseline)
    python -m scripts.check_type_ignores

    # Custom baseline path
    python -m scripts.check_type_ignores --baseline path/to/baseline.json

    # Fast staged-files scope (pre-commit hook)
    python -m scripts.check_type_ignores --staged

    # Update (create / overwrite) the baseline from current state —
    # guarded: disappearing files-keys must be named via --allow-removed
    python -m scripts.check_type_ignores --update-baseline
    python -m scripts.check_type_ignores --update-baseline \
        --allow-removed path/to/fully_cleaned_file.py

Importable
----------
    >>> from scripts.check_type_ignores import check_type_ignores
    >>> result = check_type_ignores()           # dict with scan + comparison
    >>> result = check_type_ignores("my.json")  # explicit baseline path
"""

from __future__ import annotations

from .main import check_type_ignores

__all__ = ["check_type_ignores"]
