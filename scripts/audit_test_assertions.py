#!/usr/bin/env python3
"""Thin wrapper for the test_assertion_audit package.

Usage:
    python scripts/audit_test_assertions.py [options]

See test_assertion_audit package for implementation.
"""

import sys
from pathlib import Path

# Ensure the scripts directory is on sys.path for package imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_assertion_audit.__main__ import main

sys.exit(main())
