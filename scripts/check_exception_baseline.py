#!/usr/bin/env python3
"""No-growth gate for approved architecture exceptions.

Approved exceptions are allowed to disappear without ceremony. Any new pyproject
architecture exception or adoption inline fallback must be added to the
machine-readable baseline through an ADR/user-approved review.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.architecture.baselines import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    compare_section,
    format_comparison,
    stable_fingerprint,
)

PYPROJECT_PATH = ROOT / "pyproject.toml"
ADOPTION_REGISTRY_PATH = ROOT / "scripts" / "architecture" / "adoption-registry.yaml"
EXCEPTION_BASELINE_SECTION = "approved_exceptions"


def _load_pyproject(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        msg = f"Expected YAML mapping: {path}"
        raise ValueError(msg)
    return cast("dict[str, Any]", data)


def collect_exception_fingerprints(
    pyproject_path: Path = PYPROJECT_PATH,
    adoption_registry_path: Path = ADOPTION_REGISTRY_PATH,
) -> set[str]:
    """Collect approved exception fingerprints from canonical registries."""
    items: set[str] = set()

    pyproject = _load_pyproject(pyproject_path)
    entries_raw: Any = (
        pyproject.get("tool", {})
        .get("narrare", {})
        .get("architecture", {})
        .get("exceptions", {})
        .get("entries", [])
    )
    if isinstance(entries_raw, list):
        for raw_entry in cast("list[object]", entries_raw):
            entry = cast("dict[str, object]", raw_entry) if isinstance(raw_entry, dict) else None
            if isinstance(entry, dict):
                items.add(
                    stable_fingerprint(
                        "pyproject",
                        entry.get("rule", ""),
                        entry.get("file", ""),
                        entry.get("reason", ""),
                    )
                )

    registry = _load_yaml_mapping(adoption_registry_path)
    fallbacks_raw: Any = registry.get("inline_fallbacks", []) or []
    if isinstance(fallbacks_raw, list):
        for raw_fallback in cast("list[object]", fallbacks_raw):
            fallback = (
                cast("dict[str, object]", raw_fallback) if isinstance(raw_fallback, dict) else None
            )
            if isinstance(fallback, dict):
                items.add(
                    stable_fingerprint(
                        "inline_fallback",
                        fallback.get("file", ""),
                        fallback.get("variable", ""),
                        fallback.get("migration_target", ""),
                    )
                )

    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Check approved exception no-growth baseline.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--pyproject", type=Path, default=PYPROJECT_PATH)
    parser.add_argument("--adoption-registry", type=Path, default=ADOPTION_REGISTRY_PATH)
    args = parser.parse_args()

    comparison = compare_section(
        collect_exception_fingerprints(args.pyproject, args.adoption_registry),
        EXCEPTION_BASELINE_SECTION,
        args.baseline,
    )
    print(format_comparison(comparison, "Approved exception no-growth gate"))
    if comparison.ok:
        print("RESULT: Approved exceptions did not grow")
        return 0
    print("RESULT: New approved exception(s) require ADR/user-approved baseline update")
    return 1


if __name__ == "__main__":
    sys.exit(main())
