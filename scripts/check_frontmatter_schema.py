#!/usr/bin/env python3
"""No-growth gate for frontmatter schema violations in bundled prompts.

Root cause (CR-AUFG-04-03): ``parse_frontmatter()`` in
``packages/core/narrare_core/shared/frontmatter.py`` is generic YAML parsing
with *no* schema validation. The frontmatter schema is documented in
``prompt-standards.md`` §1 (required fields: ``prompt_type``,
``prompt_language``, ``prompt_version``) but nothing enforced it, so a typo
such as ``prompt_typ:`` was silently accepted at runtime.

This checker closes that enforcement hole. It reuses the shared runtime
``parse_frontmatter()`` (so it validates exactly what the runtime sees) and
reports schema violations as **warnings**: missing required fields, unknown
fields (likely typos), invalid enum values, and malformed semver versions.

Design — WARNING-only with a clean-baseline ratchet (per the prevention-gate
rule: new prevention measures start warning-only). Existing violations may
shrink without ceremony; any *new* violation beyond the recorded baseline
fails the gate until fixed or explicitly ADR-approved.

Note: the structural checker ``check_prompt_structure.py`` already enforces
missing/invalid required fields at FAIL level via its own naive parser. This
checker is the cohesive, warning-level schema gate built on the *shared*
runtime parser, adding the previously-ungated unknown-field (typo) detection.

Usage:
    python scripts/check_frontmatter_schema.py               # ratcheted check
    python scripts/check_frontmatter_schema.py --baseline X  # custom baseline
    python scripts/check_frontmatter_schema.py --no-baseline # disable ratchet
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.architecture.baselines import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    compare_section,
    format_comparison,
    stable_fingerprint,
)

from narrare_core.shared.frontmatter import parse_frontmatter  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Mapping

FRONTMATTER_SCHEMA_SECTION = "frontmatter_schema_warnings"
BUNDLED_DIR = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"

# Schema (authoritative: docs/development/prompt-standards.md §1).
VALID_PROMPT_TYPES = frozenset(
    {
        "writing",
        "kb",
        "analysis",
        "planning",
        "meta",
        "generation",
        "wiki",
        "universal",
    }
)
VALID_LANGUAGES = frozenset({"en", "de", "fr"})
REQUIRED_FIELDS: tuple[str, ...] = (
    "prompt_type",
    "prompt_language",
    "prompt_version",
)
# For system.md files the only known frontmatter fields are the required ones;
# anything else is unknown (likely a typo or an extraneous field).
KNOWN_FIELDS = frozenset(REQUIRED_FIELDS)
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ── Schema validation (pure) ───────────────────────────────────


def _is_missing(value: Any) -> bool:
    """True when a frontmatter value is absent or empty."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def validate_frontmatter_schema(metadata: Mapping[str, Any]) -> list[str]:
    """Validate a frontmatter metadata dict against the documented schema.

    Returns a list of human-readable warning messages (empty when valid).
    Assumes frontmatter is present — the no-frontmatter case is handled by
    the collector before calling this function.
    """
    warnings: list[str] = []

    # prompt_type — required + enum.
    pt = metadata.get("prompt_type")
    if _is_missing(pt):
        warnings.append("missing required frontmatter field 'prompt_type'")
    elif pt not in VALID_PROMPT_TYPES:
        warnings.append(f"invalid prompt_type '{pt}'")

    # prompt_language — required + enum.
    pl = metadata.get("prompt_language")
    if _is_missing(pl):
        warnings.append("missing required frontmatter field 'prompt_language'")
    elif pl not in VALID_LANGUAGES:
        warnings.append(f"invalid prompt_language '{pl}'")

    # prompt_version — required + semver.
    pv = metadata.get("prompt_version")
    if _is_missing(pv):
        warnings.append("missing required frontmatter field 'prompt_version'")
    elif not SEMVER_RE.match(str(pv)):
        warnings.append(f"malformed prompt_version '{pv}' (must match semver MAJOR.MINOR.PATCH)")

    # Unknown fields — anything outside the known set is likely a typo.
    for key in metadata:
        if key not in KNOWN_FIELDS:
            warnings.append(f"unknown frontmatter field '{key}' (possible typo)")

    return warnings


# ── Discovery + collection ─────────────────────────────────────


def _is_system_md(path: Path) -> bool:
    """True for prompt system files (system.md or system.<variant>.md)."""
    name = path.name
    return name == "system.md" or name.startswith("system.")


def collect_frontmatter_schema_findings(
    bundled_dir: Path = BUNDLED_DIR,
    repo_root: Path = ROOT,
) -> set[str]:
    """Collect stable fingerprints of frontmatter schema violations.

    Discovers ``system*.md`` files under *bundled_dir*, parses each with the
    shared runtime ``parse_frontmatter()``, validates the metadata against the
    schema, and returns a set of fingerprints of the form
    ``"<repo-relative-path> | <warning-message>"``.
    """
    findings: set[str] = set()
    if not bundled_dir.is_dir():
        return findings

    for path in sorted(bundled_dir.rglob("*.md")):
        if not _is_system_md(path):
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            rel = path.relative_to(repo_root).as_posix()
        except ValueError:
            rel = path.as_posix()

        parsed = parse_frontmatter(text)
        if not parsed.has_frontmatter:
            findings.add(stable_fingerprint(rel, "missing YAML frontmatter"))
            continue

        for message in validate_frontmatter_schema(parsed.metadata):
            findings.add(stable_fingerprint(rel, message))

    return findings


# ── CLI ────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="No-growth gate for frontmatter schema violations.",
    )
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--bundled-dir", type=Path, default=BUNDLED_DIR)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Disable the ratchet comparison (always exit 0 unless an error).",
    )
    args = parser.parse_args()

    findings = collect_frontmatter_schema_findings(args.bundled_dir, args.repo_root)

    if args.no_baseline:
        for item in sorted(findings):
            print(item)
        print(f"RESULT: {len(findings)} frontmatter schema warning(s) (ratchet disabled)")
        return 0

    comparison = compare_section(findings, FRONTMATTER_SCHEMA_SECTION, args.baseline)
    print(format_comparison(comparison, "Frontmatter schema warnings"))
    if comparison.ok:
        print("RESULT: No new frontmatter schema violations")
        return 0
    print("RESULT: New frontmatter schema violation(s) require baseline update")
    return 1


if __name__ == "__main__":
    sys.exit(main())
