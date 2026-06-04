#!/usr/bin/env python3
"""Thin wrapper for the eval_drift package.

Usage:
    python scripts/check_eval_drift.py [options]

See eval_drift package for implementation.
"""

import sys
from pathlib import Path

# Ensure the scripts directory is on sys.path for package imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_drift.__main__ import main

sys.exit(main())
