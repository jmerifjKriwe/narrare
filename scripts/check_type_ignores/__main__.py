"""CLI entry point for check-type-ignores discipline (RULE-23).

Usage:
    python -m scripts.check_type_ignores
    python -m scripts.check_type_ignores --staged
    python -m scripts.check_type_ignores --update-baseline [--allow-removed f.py]
    python -m scripts.check_type_ignores --baseline path/to/baseline.json
"""

from __future__ import annotations

import sys

from scripts.check_type_ignores.main import main

if __name__ == "__main__":
    sys.exit(main())
