"""Tool version consistency checks (Node.js, pnpm).

Reads the canonical version from SSOT files and validates that all
infrastructure and documentation files stay in sync.

SSOT sources:
  - Node.js: hardcoded EXPECTED_NODE_VERSION (aligned with TECH_STACK.md)
  - pnpm: ``package.json`` ``packageManager`` field

Check families:
    - Node.js version consistency across Dockerfiles, CI, README, docs
    - pnpm version consistency across Dockerfiles, CI, docs

See: ADR-041 Decision 2, docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# ── Data model ─────────────────────────────────────────────────


@dataclass
class CheckResult:
    """Result of a single drift check against one file/pattern pair."""

    file: str
    pattern: str
    passed: bool
    detail: str = ""


# ── Constants ──────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXPECTED_NODE_VERSION = "24"

# Regex to extract pnpm version from package.json "packageManager" field.
_PNPM_VERSION_RE = re.compile(r'"packageManager":\s*"pnpm@(\d+\.\d+\.\d+)"')


# ── Helpers ────────────────────────────────────────────────────


def _read_file(path: str) -> str | None:
    """Read a file relative to REPO_ROOT."""
    full_path = REPO_ROOT / path
    if not full_path.exists():
        return None
    try:
        return full_path.read_text(encoding="utf-8")
    except Exception:
        return None


def _read_pnpm_version_from_package_json() -> str | None:
    """Extract pnpm version from root ``package.json``."""
    content = _read_file("package.json")
    if content is None:
        return None
    m = _PNPM_VERSION_RE.search(content)
    return m.group(1) if m else None


def _tool_check(
    path: str,
    pattern: str,
    *,
    min_count: int = 1,
    label: str | None = None,
) -> CheckResult:
    """Check a file for a version-related pattern."""
    display_name = label or path
    full_path = REPO_ROOT / path

    if not full_path.exists():
        return CheckResult(
            file=display_name,
            pattern=pattern,
            passed=True,
            detail="⚠  File not found — skipped",
        )

    content = _read_file(path)
    if content is None:
        return CheckResult(
            file=display_name,
            pattern=pattern,
            passed=False,
            detail=f"Error reading {path}",
        )

    matches = re.findall(pattern, content)
    match_count = len(matches)

    if match_count >= min_count:
        return CheckResult(
            file=display_name,
            pattern=pattern,
            passed=True,
            detail=f"Found {match_count} match(es) matching /{pattern}/",
        )

    return CheckResult(
        file=display_name,
        pattern=pattern,
        passed=False,
        detail=(f"Expected ≥{min_count} match(es) of /{pattern}/ but found {match_count}"),
    )


# ── Node.js checks ────────────────────────────────────────────


def register_node_checks() -> list[tuple[str, Callable[[], list[CheckResult]]]]:
    """Register Node.js version drift checks."""
    v = EXPECTED_NODE_VERSION
    checks: list[tuple[str, Callable[[], list[CheckResult]]]] = []

    checks.append(
        (
            "README.md Node version",
            lambda v=v: [
                _tool_check(
                    "README.md",
                    rf"Node\.js\s+(?:{v}\+|≥\s*{v})",
                    label="README.md",
                ),
            ],
        )
    )
    checks.append(
        (
            "Deployment guide Node version (x2)",
            lambda v=v: [
                _tool_check(
                    "docs/development/deployment-guide.md",
                    rf"Node\.js\s+{v}\+",
                    min_count=2,
                    label="docs/development/deployment-guide.md",
                ),
            ],
        )
    )
    checks.append(
        (
            "Context deployment guide Node version",
            lambda v=v: [
                _tool_check(
                    ".opencode/context/narrare-dev/guides/deployment.md",
                    rf"Node\.js\s+{v}\+",
                    label=".opencode/context/narrare-dev/guides/deployment.md",
                ),
            ],
        )
    )
    checks.append(
        (
            "Evals README Node version",
            lambda v=v: [
                _tool_check(
                    "evals/README.md",
                    rf"Node\.js\s+≥\s*{v}",
                    label="evals/README.md",
                ),
            ],
        )
    )
    checks.append(
        (
            "CI workflow Node version (x2)",
            lambda v=v: [
                _tool_check(
                    ".github/workflows/ci.yml",
                    rf'node-version:\s*"{v}"',
                    min_count=2,
                    label=".github/workflows/ci.yml",
                ),
            ],
        )
    )
    checks.append(
        (
            "Eval workflow Node version",
            lambda v=v: [
                _tool_check(
                    ".github/workflows/eval.yml",
                    rf'node-version:\s*"{v}"',
                    label=".github/workflows/eval.yml",
                ),
            ],
        )
    )
    checks.append(
        (
            "Web package.json engines.node",
            lambda v=v: [
                _tool_check(
                    "packages/web/package.json",
                    rf'">={v}',
                    label="packages/web/package.json (engines.node)",
                ),
            ],
        )
    )

    return checks


# ── pnpm checks ────────────────────────────────────────────────


def register_pnpm_checks(
    ssot_version: str,
) -> list[tuple[str, Callable[[], list[CheckResult]]]]:
    """Register pnpm version drift checks against *ssot_version*."""
    v = ssot_version
    checks: list[tuple[str, Callable[[], list[CheckResult]]]] = []

    checks.append(
        (
            "DevContainer Dockerfile pnpm version",
            lambda v=v: [
                _tool_check(
                    ".devcontainer/Dockerfile",
                    rf"PNPM_VERSION={re.escape(v)}",
                    label=".devcontainer/Dockerfile",
                ),
            ],
        )
    )
    checks.append(
        (
            "Production Dockerfile pnpm version",
            lambda v=v: [
                _tool_check(
                    "Dockerfile",
                    rf"PNPM_VERSION={re.escape(v)}",
                    label="Dockerfile",
                ),
            ],
        )
    )
    checks.append(
        (
            "Deployment guide pnpm version",
            lambda v=v: [
                _tool_check(
                    "docs/development/deployment-guide.md",
                    rf"pnpm\s+{re.escape(v)}",
                    label="docs/development/deployment-guide.md",
                ),
            ],
        )
    )
    checks.append(
        (
            "TECH_STACK.md pnpm version",
            lambda v=v: [
                _tool_check(
                    "docs/_shared/TECH_STACK.md",
                    rf"pnpm\s+`?{re.escape(v)}`?",
                    label="docs/_shared/TECH_STACK.md",
                ),
            ],
        )
    )
    checks.append(
        (
            "CI workflow pnpm version",
            lambda v=v: [
                _tool_check(
                    ".github/workflows/ci.yml",
                    rf"version:\s*{re.escape(v)}",
                    min_count=1,
                    label=".github/workflows/ci.yml",
                ),
            ],
        )
    )

    return checks


# ── Combined public API ────────────────────────────────────────


def register_tool_checks() -> list[tuple[str, Callable[[], list[CheckResult]]]]:
    """Register all tool version checks (Node.js + pnpm).

    Reads the canonical pnpm version from ``package.json`` and registers
    both Node and pnpm consistency checks.
    """
    checks = register_node_checks()

    pnpm_version = _read_pnpm_version_from_package_json()
    if pnpm_version is not None:
        checks.extend(register_pnpm_checks(pnpm_version))

    return checks
