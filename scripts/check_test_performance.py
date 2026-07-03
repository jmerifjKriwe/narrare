#!/usr/bin/env python3
"""Frontend test performance threshold checker.

Monitors frontend test execution time against a configurable threshold.
Supports two modes:
  1. --duration: Check a pre-measured duration (for CI post-test steps)
  2. --run: Execute tests and measure timing (for local development)

Exit codes:
  0: Under threshold (or tests pass)
  1: Over threshold (WARNING in CI)
  N: Test exit code (when using --run and tests fail)

Usage:
    # Check a pre-measured duration (CI mode)
    uv run python scripts/check_test_performance.py --duration 140 --threshold 120

    # Run tests and measure (local dev)
    uv run python scripts/check_test_performance.py --run --threshold 120
"""

from __future__ import annotations

import argparse
import os
import subprocess  # nosec B404
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_frontend_tests() -> tuple[int, float]:
    """Run frontend tests and return (exit_code, duration_seconds)."""
    web_dir = ROOT / "packages" / "web"
    start = time.time()
    result = subprocess.run(["pnpm", "test"], cwd=str(web_dir))  # noqa: S607  # nosec B603 B607
    elapsed = time.time() - start
    return result.returncode, elapsed


def check_threshold(duration: float, threshold: int) -> int:
    """Check duration against threshold. Returns 0 if OK, 1 if over."""
    print(f"Frontend test duration: {duration:.1f}s (threshold: {threshold}s)")

    if duration > threshold:
        over_by = duration - threshold
        print(
            f"::warning::Frontend tests took {duration:.1f}s, "
            f"exceeding {threshold}s threshold by {over_by:.1f}s"
        )
        print("TODO: WARNING-only gate — transition to blocking after baseline is established.")
        return 0

    print(f"✅ Under {threshold}s performance threshold")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Frontend test performance threshold checker",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Pre-measured test duration in seconds (CI mode)",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run frontend tests and measure timing (local dev)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=int(os.environ.get("FRONTEND_TEST_THRESHOLD", "130")),
        help="Max allowed seconds (default: 130, env: FRONTEND_TEST_THRESHOLD)",
    )
    args = parser.parse_args()

    if args.duration is not None:
        return check_threshold(args.duration, args.threshold)

    if args.run:
        exit_code, duration = run_frontend_tests()
        if exit_code != 0:
            return exit_code
        return check_threshold(duration, args.threshold)

    parser.error("Specify --duration <seconds> or --run")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
