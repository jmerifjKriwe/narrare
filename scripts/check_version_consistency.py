#!/usr/bin/env python3
"""
Narrare Workspace Version Consistency Checker.

Detects dependency version drift across workspace members.
Dependabot updates each pyproject.toml independently — this check
ensures shared dev dependencies stay in sync.

Exit code 0: all versions consistent.
Exit code 1: version drift detected.

See: docs/_shared/CONSTRAINTS.md
"""

from __future__ import annotations

import sys
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent


def parse_version(dep_spec: str) -> str:
    """Extract version spec from a dependency string like 'pyright==1.1.410'.

    Returns the version constraint part (e.g. '==1.1.410', '>=7.0.0,<8').
    Returns '' for unversioned deps (e.g. workspace references).
    """
    # Strip extras like [openai,anthropic]
    dep_spec = dep_spec.split("[")[0] if "[" in dep_spec else dep_spec
    # Strip semver markers and find first version operator
    for op in ("==", ">=", "<=", "~=", "!=", "><", ">"):
        idx = dep_spec.find(op)
        if idx != -1:
            return dep_spec[idx:].strip()
    for op in ("<",):
        idx = dep_spec.find(op)
        if idx != -1:
            return dep_spec[idx:].strip()
    return ""


def extract_deps(pyproject_path: Path) -> dict[str, str]:
    """Extract all dependencies with their version specs from a pyproject.toml."""
    if not pyproject_path.exists():
        return {}

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    deps: dict[str, str] = {}
    # [project].dependencies
    for dep in data.get("project", {}).get("dependencies", []):
        dep = dep.strip()
        if not dep:
            continue
        # Skip workspace references (no version spec)
        name = (
            dep.split("[")[0]
            .split(">")[0]
            .split("<")[0]
            .split("=")[0]
            .split("!")[0]
            .split("~")[0]
            .strip()
        )
        version = parse_version(dep)
        if version:
            deps[name] = version

    # [dependency-groups].dev
    for dep in data.get("dependency-groups", {}).get("dev", []):
        dep = dep.strip()
        if not dep:
            continue
        name = (
            dep.split("[")[0]
            .split(">")[0]
            .split("<")[0]
            .split("=")[0]
            .split("!")[0]
            .split("~")[0]
            .strip()
        )
        version = parse_version(dep)
        if version:
            deps[name] = version

    return deps


def main() -> int:
    root_pyproject = ROOT / "pyproject.toml"
    with root_pyproject.open("rb") as f:
        root_data = tomllib.load(f)

    # Discover workspace members
    members = ["."]  # root
    for member_path in (
        root_data.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    ):
        members.append(member_path)

    # Collect deps per member
    all_deps: dict[str, dict[str, str]] = {}
    for member in members:
        pyproject = ROOT / member / "pyproject.toml"
        deps = extract_deps(pyproject)
        if deps:
            all_deps[member] = deps

    # Find shared packages and check consistency
    package_locations: dict[str, dict[str, str]] = defaultdict(dict)
    for member, deps in all_deps.items():
        for pkg, version in deps.items():
            package_locations[pkg][member] = version

    # Check for drift in shared packages
    drifts: list[tuple[str, dict[str, str]]] = []
    shared_count = 0
    for pkg, locations in sorted(package_locations.items()):
        if len(locations) < 2:
            continue
        shared_count += 1
        versions = set(locations.values())
        if len(versions) > 1:
            drifts.append((pkg, locations))

    if drifts:
        print(f"❌ Version drift detected for {len(drifts)} package(s):\n")
        for pkg, locations in drifts:
            print(f"  {pkg}:")
            for path, version in sorted(locations.items()):
                label = path if path != "." else "pyproject.toml (root)"
                marker = "  ← MISMATCH" if version != next(iter(locations.values())) else ""
                print(f"    {label:40s} {version}{marker}")
            print()
        in_sync = shared_count - len(drifts)
        if in_sync > 0:
            unit = "dependency is" if in_sync == 1 else "dependencies are"
            print(f"✅ {in_sync} other shared {unit} in sync.")
        return 1

    if shared_count > 0:
        unit = "dependency is" if shared_count == 1 else "dependencies are"
        print(f"✅ All {shared_count} shared {unit} in sync.")
    else:
        print("INFO: No shared dependencies found across workspace members.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
