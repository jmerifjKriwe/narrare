#!/usr/bin/env python3
"""No-growth gate for approved architecture exceptions.

Approved exceptions are allowed to disappear without ceremony. Any new pyproject
architecture exception or adoption inline fallback must be added to the
machine-readable baseline through an ADR/user-approved review.

Modes:
  default         No-growth gate against ai-gate-baseline.json.
  --check-sync    Verify pyproject.toml exceptions ↔ CONSTRAINTS.md §7 table sync.
"""

from __future__ import annotations

import argparse
import re
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
CONSTRAINTS_PATH = ROOT / "docs" / "_shared" / "CONSTRAINTS.md"
EXCEPTION_BASELINE_SECTION = "approved_exceptions"

# Regex for CONSTRAINTS.md §7 table rows:  | # | RULE-XX | `file` | ... |
_TABLE_ROW_RE = re.compile(
    r"^\|\s*\d+\s*\|\s*(RULE-[\w-]+)\s*\|\s*`([^`]+)`\s*\|",
    re.MULTILINE,
)

# Extended regex capturing reason column (4th column) as well.
_TABLE_ROW_FULL_RE = re.compile(
    r"^\|\s*\d+\s*\|\s*(RULE-[\w-]+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|",
    re.MULTILINE,
)


def _normalize_reason(text: str) -> str:
    """Normalize reason text for fuzzy comparison (case-insensitive, strip trailing period)."""
    return text.strip().rstrip(".").rstrip().lower()


def _key_terms(text: str) -> set[str]:
    """Extract significant terms (>= 4 chars, excluding common stopwords)."""
    stopwords = frozenset(
        {
            "that",
            "this",
            "with",
            "from",
            "here",
            "have",
            "been",
            "were",
            "will",
        }
    )
    return set(re.findall(r"[a-zA-Z0-9_-]{4,}", text.lower())) - stopwords


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


def _parse_pyproject_entries(pyproject_path: Path) -> dict[tuple[str, str], str]:
    """Extract (rule, file) -> reason mapping from pyproject.toml exception entries."""
    pyproject = _load_pyproject(pyproject_path)
    entries_raw: Any = (
        pyproject.get("tool", {})
        .get("narrare", {})
        .get("architecture", {})
        .get("exceptions", {})
        .get("entries", [])
    )
    entries: dict[tuple[str, str], str] = {}
    if isinstance(entries_raw, list):
        for raw_entry in cast("list[object]", entries_raw):
            entry = cast("dict[str, object]", raw_entry) if isinstance(raw_entry, dict) else None
            if isinstance(entry, dict):
                rule = str(entry.get("rule", ""))
                file_ = str(entry.get("file", ""))
                reason = str(entry.get("reason", ""))
                if rule and file_:
                    entries[(rule, file_)] = reason
    return entries


def _parse_constraints_entries(constraints_path: Path) -> dict[tuple[str, str], str]:
    """Extract (rule, file) -> reason mapping from CONSTRAINTS.md §7 table."""
    text = constraints_path.read_text(encoding="utf-8")
    entries: dict[tuple[str, str], str] = {}
    for match in _TABLE_ROW_FULL_RE.finditer(text):
        rule = match.group(1).strip()
        file_ = match.group(2).strip()
        reason = match.group(3).strip()
        if rule and file_:
            entries[(rule, file_)] = reason
    return entries


def _parse_pyproject_pairs(pyproject_path: Path) -> set[tuple[str, str]]:
    """Extract (rule, file) pairs from pyproject.toml exception entries."""
    return set(_parse_pyproject_entries(pyproject_path).keys())


def _parse_constraints_pairs(constraints_path: Path) -> set[tuple[str, str]]:
    """Extract (rule, file) pairs from CONSTRAINTS.md §7 table."""
    return set(_parse_constraints_entries(constraints_path).keys())


def check_sync(
    pyproject_path: Path = PYPROJECT_PATH,
    constraints_path: Path = CONSTRAINTS_PATH,
) -> int:
    """Verify pyproject.toml exceptions ↔ CONSTRAINTS.md §7 table are in sync.

    Checks:
      1. Existence: every (rule, file) pair exists in both sources (blocking).
      2. Consistency: reason text matches between sources (non-blocking warnings).
    """
    pyproject_pairs = _parse_pyproject_pairs(pyproject_path)
    constraints_pairs = _parse_constraints_pairs(constraints_path)

    missing_in_constraints = pyproject_pairs - constraints_pairs
    missing_in_pyproject = constraints_pairs - pyproject_pairs

    ok = True

    if missing_in_constraints:
        ok = False
        print("MISSING in CONSTRAINTS.md §7 table:")
        for rule, file_ in sorted(missing_in_constraints):
            print(f"  {rule} {file_}")

    if missing_in_pyproject:
        ok = False
        print("MISSING in pyproject.toml [tool.narrare.architecture.exceptions.entries]:")
        for rule, file_ in sorted(missing_in_pyproject):
            print(f"  {rule} {file_}")

    # --- Reason consistency check (warnings only, non-blocking) ---
    common_pairs = pyproject_pairs & constraints_pairs
    warnings: list[str] = []
    if common_pairs:
        pp_entries = _parse_pyproject_entries(pyproject_path)
        cm_entries = _parse_constraints_entries(constraints_path)

        for pair in sorted(common_pairs):
            pp_reason = pp_entries.get(pair, "")
            cm_reason = cm_entries.get(pair, "")

            if not cm_reason:
                warnings.append(f"{pair[0]} {pair[1]}: empty reason in CONSTRAINTS.md")
            elif _normalize_reason(pp_reason) != _normalize_reason(cm_reason):
                # Fuzzy check: compare key-term overlap
                pp_terms = _key_terms(pp_reason)
                cm_terms = _key_terms(cm_reason)
                if pp_terms and cm_terms:
                    overlap = pp_terms & cm_terms
                    ratio = len(overlap) / max(len(pp_terms), len(cm_terms))
                    if ratio < 0.5:
                        warnings.append(
                            f"{pair[0]} {pair[1]}: reason text differs significantly "
                            f"(overlap {ratio:.0%})"
                        )
                elif not cm_terms:
                    warnings.append(
                        f"{pair[0]} {pair[1]}: no significant terms in CONSTRAINTS.md reason"
                    )

    if warnings:
        print("\nWARNINGS — Reason text mismatch (non-blocking):")
        for w in warnings:
            print(f"  {w}")

    if ok:
        n_warnings = len(warnings)
        suffix = f" ({n_warnings} warning{'s' if n_warnings != 1 else ''})" if n_warnings else ""
        print(f"RESULT: Exception sync OK — {len(pyproject_pairs)} entries match{suffix}")
        return 0

    print(
        f"\nRESULT: Exception sync FAILED — "
        f"pyproject.toml has {len(pyproject_pairs)} entries, "
        f"CONSTRAINTS.md has {len(constraints_pairs)} entries"
    )
    return 1


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
    parser.add_argument(
        "--check-sync",
        action="store_true",
        default=False,
        help="Verify pyproject.toml exceptions ↔ CONSTRAINTS.md §7 table sync.",
    )
    parser.add_argument(
        "--constraints",
        type=Path,
        default=CONSTRAINTS_PATH,
        help="Path to CONSTRAINTS.md (used with --check-sync).",
    )
    args = parser.parse_args()

    if args.check_sync:
        return check_sync(args.pyproject, args.constraints)

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
