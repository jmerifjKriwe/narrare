"""Test configuration for AI interaction checker tests.

Adds ``scripts/checks/`` to ``sys.path`` so that ``_ai_interaction_checks``
is importable as a top-level package (matching how the main checker
script imports it).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_CHECKS_DIR = _ROOT / "scripts" / "checks"

if str(_CHECKS_DIR) not in sys.path:
    sys.path.insert(0, str(_CHECKS_DIR))
