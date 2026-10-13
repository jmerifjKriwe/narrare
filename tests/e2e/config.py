"""E2E runtime configuration: stack URLs + dev-user credentials.

Single source of truth for where the E2E suite finds the stack. Shared by
``tests/e2e/conftest.py`` and ``tests/e2e/foundation.py`` (RULE-04: neither
duplicates the env-var contract).

Env contract (mirrors ``scripts/run_e2e.sh``):
- ``E2E_BASE_URL`` — frontend origin (default ``http://localhost:3000``).
- ``E2E_API_URL`` — API origin (default ``http://localhost:8000``).
"""

from __future__ import annotations

import os

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
API_URL = os.environ.get("E2E_API_URL", "http://localhost:8000")

# Dev user credentials (seeded by scripts/seed_dev_user.py)
DEV_EMAIL = "dev@narrare.dev"
DEV_PASSWORD = "narrare-dev"
