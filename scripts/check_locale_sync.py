#!/usr/bin/env python3
"""
Narrare Locale Sync Checker.

Detects locale drift between EN/DE/FR prompt variants by comparing
variables and section headings across locales for the same prompt mode.

Exit codes:
  0: All locale groups are synced.
  1: Drift detected.

Usage:
  python scripts/check_locale_sync.py
  python scripts/check_locale_sync.py --verbose
  python scripts/check_locale_sync.py --help
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
BUNDLED_DIR = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"

VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")
HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ── Data structures ────────────────────────────────────────────


@dataclass
class LocaleVariant:
    """One locale variant of a prompt."""

    locale: str
    path: Path
    rel_path: str
    variables: set[str] = field(default_factory=set[str])
    headings: list[str] = field(default_factory=list[str])


@dataclass
class SyncGroup:
    """A group of locale variants for the same prompt mode."""

    group_key: str  # e.g., "kb/interview", "writing/extend_chapter"
    variants: dict[str, LocaleVariant] = field(default_factory=dict[str, LocaleVariant])

    @property
    def all_variables(self) -> set[str]:
        result: set[str] = set()
        for v in self.variants.values():
            result |= v.variables
        return result


# ── Parsing ────────────────────────────────────────────────────


def parse_locale_file(path: Path, bundled_dir: Path) -> tuple[str, str, LocaleVariant] | None:
    """Parse a system.md file. Returns (group_key, locale, variant) or None."""
    rel = path.relative_to(bundled_dir)
    parts = rel.parts

    # Only process system.md files (not tones, name-styles, etc.).
    if not (path.name == "system.md" or path.name.startswith("system.")):
        return None

    # Extract structure: category/locale/[subdirs...]/system.md
    if len(parts) < 3:
        return None

    category = parts[0]
    locale = parts[1]

    # Validate locale.
    if locale not in {"en", "de", "fr"}:
        return None

    # Mode is everything between locale and filename.
    mode = "/".join(parts[2:-1]) if len(parts) > 3 else ""

    group_key = f"{category}/{mode}" if mode else category

    text = path.read_text(encoding="utf-8")

    # Remove frontmatter before extracting headings.
    fm_match = _FRONTMATTER_RE.match(text)
    content = text[fm_match.end() :] if fm_match else text

    variant = LocaleVariant(
        locale=locale,
        path=path,
        rel_path=str(rel),
        variables=set(VARIABLE_RE.findall(text)),
        headings=[m.group(1).strip() for m in HEADING_RE.finditer(content)],
    )

    return group_key, locale, variant


# ── Discovery ──────────────────────────────────────────────────


def discover_groups(bundled_dir: Path) -> dict[str, SyncGroup]:
    """Discover all locale groups."""
    groups: dict[str, SyncGroup] = {}

    for md_file in sorted(bundled_dir.rglob("system.md")):
        result = parse_locale_file(md_file, bundled_dir)
        if result is None:
            continue
        group_key, locale, variant = result
        if group_key not in groups:
            groups[group_key] = SyncGroup(group_key=group_key)
        groups[group_key].variants[locale] = variant

    # Also handle system.*.md variants (e.g., system.lite.md).
    for md_file in sorted(bundled_dir.rglob("system.*.md")):
        if md_file.name == "system.md":
            continue
        result = parse_locale_file(md_file, bundled_dir)
        if result is None:
            continue
        group_key, locale, variant = result
        # Use a modified key for variant files.
        suffix = md_file.suffixes[0].lstrip(".")
        variant_key = f"{group_key} [{suffix}]"
        if variant_key not in groups:
            groups[variant_key] = SyncGroup(group_key=variant_key)
        groups[variant_key].variants[locale] = variant

    return groups


# ── Sync checking ──────────────────────────────────────────────


@dataclass
class DriftReport:
    """Report of locale drift for a group."""

    group_key: str
    synced: bool = True
    variable_drifts: list[str] = field(default_factory=list[str])
    heading_drifts: list[str] = field(default_factory=list[str])


def check_sync(group: SyncGroup) -> DriftReport:
    """Check a single group for locale drift."""
    report = DriftReport(group_key=group.group_key)

    if len(group.variants) < 2:
        # Single locale — nothing to compare.
        return report

    all_vars = group.all_variables

    # ── Variable drift check ──────────────────────────────────
    for locale, variant in sorted(group.variants.items()):
        missing_vars = all_vars - variant.variables
        if missing_vars:
            report.synced = False
            for var in sorted(missing_vars):
                has_in = [
                    loc for loc, v in group.variants.items() if loc != locale and var in v.variables
                ]
                report.variable_drifts.append(
                    f"  {locale.upper()}: MISSING {{{{{var}}}}} "
                    f"(present in {', '.join(sorted(has_in))})"
                )

    # ── Heading structure drift check ─────────────────────────
    # Headings in different locales are translations, so we compare
    # heading *levels and counts*, not the text content.
    from collections import Counter

    def heading_signature(headings: list[str]) -> str:
        """Create a structural signature from headings (level counts)."""
        levels: list[str] = []
        for h in headings:
            stripped = h.lstrip("#")
            level = len(h) - len(stripped)
            levels.append(f"h{level}")
        counts = Counter(levels)
        return ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))

    base_sig: str | None = None
    base_locale: str | None = None
    for locale, variant in sorted(group.variants.items()):
        sig = heading_signature(variant.headings)
        if base_sig is None:
            base_sig = sig
            base_locale = locale
        elif sig != base_sig and base_locale is not None:
            report.synced = False
            report.heading_drifts.append(
                f"  {locale.upper()}: heading structure differs from "
                f"{base_locale.upper()} ({sig} vs {base_sig})"
            )

    return report


# ── Reporting ──────────────────────────────────────────────────


def print_sync_report(groups: dict[str, SyncGroup], verbose: bool) -> int:
    """Print the full sync report and return exit code."""
    reports: list[DriftReport] = []
    for group in groups.values():
        reports.append(check_sync(group))

    synced_count = sum(1 for r in reports if r.synced)
    drifted_count = sum(1 for r in reports if not r.synced)

    print()
    print("LOCALE SYNC REPORT")
    print("=" * 50)
    print()

    # Print synced groups first (compact).
    if not verbose:
        synced_reports = [r for r in reports if r.synced]
        if synced_reports:
            for r in synced_reports:
                print(f"{r.group_key}:")

                # Show variable list per locale.
                group = groups[r.group_key]
                for locale in sorted(group.variants):
                    v = group.variants[locale]
                    vars_str = ", ".join("{{" + var + "}}" for var in sorted(v.variables))
                    print(f"  {locale.upper()}: {vars_str}")
                print("  ✅ SYNCED")
                print()

    # Print drifted groups with details.
    drifted_reports = [r for r in reports if not r.synced]
    for r in sorted(drifted_reports, key=lambda x: x.group_key):
        group = groups[r.group_key]

        if verbose or not r.synced:
            print(f"{r.group_key}:")
            for locale in sorted(group.variants):
                v = group.variants[locale]
                vars_str = ", ".join("{{" + var + "}}" for var in sorted(v.variables))
                print(f"  {locale.upper()}: [{vars_str}]")

        if r.variable_drifts:
            for drift in r.variable_drifts:
                print(drift)

        if r.heading_drifts:
            for drift in r.heading_drifts:
                print(drift)

        if r.variable_drifts or r.heading_drifts:
            total_missing = len(r.variable_drifts)
            print(f"  ⚠️ DRIFT DETECTED ({total_missing} variable difference(s))")
        else:
            print("  ✅ SYNCED")
        print()

    # Summary.
    print("=" * 50)
    print(f"Groups checked: {len(reports)}")
    print(f"Synced: {synced_count}")
    print(f"Drifted: {drifted_count}")
    print()

    return 1 if drifted_count > 0 else 0


# ── Main ───────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check locale sync between EN/DE/FR prompt variants.",
        epilog="Run from project root. Scans packages/core/narrare_core/prompts/_bundled/.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all groups including synced ones with full details.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=BUNDLED_DIR,
        help="Path to _bundled/ directory (default: auto-detected).",
    )
    args = parser.parse_args()

    bundled_dir = args.path
    if not bundled_dir.is_dir():
        print(f"ERROR: Prompt directory not found: {bundled_dir}", file=sys.stderr)
        return 1

    groups = discover_groups(bundled_dir)
    if not groups:
        print("WARN: No locale groups found.")
        return 0

    return print_sync_report(groups, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
