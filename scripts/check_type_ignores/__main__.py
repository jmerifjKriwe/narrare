"""CLI entry point for check-type-ignores discipline (RULE-23).

Usage:
    python -m scripts.check_type_ignores
    python -m scripts.check_type_ignores --update
    python -m scripts.check_type_ignores --baseline path/to/baseline.json
"""

from __future__ import annotations

import sys

from scripts.check_type_ignores.main import main

if __name__ == "__main__":
    sys.exit(main())
