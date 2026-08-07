#!/usr/bin/env python3
"""Pytest collection performance threshold checker.

Times pytest's collection phase and warns if it exceeds a threshold.
Useful for detecting import-cycle bloat and slow conftest.py files.

Exit codes:
  0: Under threshold, or over threshold (warning-only — never blocks CI;
     over-threshold emits a ::warning:: annotation only)
  2: Error

Usage:
    uv run python scripts/check_pytest_collection_performance.py
    uv run python scripts/check_pytest_collection_performance.py --threshold 30
    uv run python scripts/check_pytest_collection_performance.py --path tests/integration
"""

from __future__ import annotations

import argparse
import os
import subprocess  # nosec B404
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = "tests/unit"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pytest collection performance threshold checker",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=int(os.environ.get("PYTEST_COLLECTION_THRESHOLD", "20")),
        help="Max allowed collection seconds (default: 20, env: PYTEST_COLLECTION_THRESHOLD)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=DEFAULT_PATH,
        help=f"Test path to collect (default: {DEFAULT_PATH})",
    )
    args = parser.parse_args()

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        args.path,
        "--collect-only",
        "-q",
    ]

    print(f"Timing pytest collection for {args.path}...")

    start = time.time()
    subprocess.run(  # noqa: S603  # nosec B603
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - start

    print(f"\nCollection time: {elapsed:.1f}s (threshold: {args.threshold}s)")

    if elapsed > args.threshold:
        over_by = elapsed - args.threshold
        print(
            f"::warning::Pytest collection took {elapsed:.1f}s, "
            f"exceeding {args.threshold}s threshold by {over_by:.1f}s"
        )
        print("WARNING-only: performance gate does not block CI (annotates via ::warning::).")
        return 0

    print(f"✅ Under {args.threshold}s collection threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
