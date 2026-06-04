#!/usr/bin/env python3
"""Thin wrapper for the test_coverage_gaps package.

Usage:
    python scripts/check_test_coverage_gaps.py [options]

See test_coverage_gaps package for implementation.
"""

import sys
from pathlib import Path

# Ensure the scripts directory is on sys.path for package imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_coverage_gaps.__main__ import main

sys.exit(main())
