#!/usr/bin/env python3
"""Repository secret-scanning gate backed by Gitleaks.

This wrapper keeps the local developer command and CI invocation aligned:
Gitleaks must scan the repository source with redacted findings and the tracked
project config. The wrapper deliberately does not hide findings or create a
baseline; if historical findings appear, they must be reviewed and explicitly
baselined by a follow-up governance decision.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess  # nosec B404 - fixed argv, no shell invocation
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / ".gitleaks.toml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the secret-scanning gate."""
    parser = argparse.ArgumentParser(
        description="Narrare secret-scanning gate (Gitleaks)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0    No secrets found\n"
            "  1    Gitleaks found one or more unapproved secrets\n"
            "  2    Wrapper/configuration error\n"
            "  127  Gitleaks binary is not installed\n"
        ),
    )
    parser.add_argument(
        "--source",
        default=str(ROOT),
        help="Repository path to scan (default: project root)",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to .gitleaks.toml config (default: project root config)",
    )
    parser.add_argument(
        "--binary",
        default="gitleaks",
        help="Gitleaks executable name or path (default: gitleaks)",
    )
    return parser.parse_args(argv)


def build_gitleaks_command(binary: str, source: Path, config: Path) -> list[str]:
    """Build the required Gitleaks command line."""
    return [
        binary,
        "detect",
        "--source",
        str(source),
        "--redact",
        "--config",
        str(config),
    ]


def _missing_binary_message(binary: str) -> str:
    """Return actionable local installation guidance for a missing binary."""
    return (
        f"Gitleaks binary not found: {binary}\n"
        "Install Gitleaks before running the secret-scanning gate.\n"
        "Linux example: download the latest release from "
        "https://github.com/gitleaks/gitleaks/releases and place `gitleaks` on PATH.\n"
        "Then re-run: just check-secrets"
    )


def main(argv: list[str] | None = None) -> int:
    """Run the Gitleaks secret-scanning gate."""
    args = parse_args(argv)
    binary_name = str(args.binary)
    source_arg = str(args.source)
    config_arg = str(args.config)
    binary = shutil.which(binary_name)
    if binary is None:
        print(_missing_binary_message(binary_name), file=sys.stderr)
        return 127

    source = Path(source_arg).expanduser().resolve()
    config = Path(config_arg).expanduser().resolve()
    if not source.exists():
        print(f"Secret scan source does not exist: {source}", file=sys.stderr)
        return 2
    if not config.is_file():
        print(f"Gitleaks config not found: {config}", file=sys.stderr)
        return 2

    command = build_gitleaks_command(binary, source, config)
    cwd = source if source.is_dir() else source.parent
    result = subprocess.run(command, cwd=cwd, check=False)  # noqa: S603  # nosec  # controlled gitleaks invocation
    return int(result.returncode)


if __name__ == "__main__":
    sys.exit(main())
