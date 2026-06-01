#!/usr/bin/env python3
"""
Narrare German Prompt Quality Checker.

Validates DE locale prompt files for common translation quality issues:
  1. Incorrectly split compound nouns (Compound-Splitting)
  2. Denglisch / unnecessary anglicisms
  3. Mixed-language sentences (covered via Denglisch patterns)

Exit codes:
  0: No issues found
  1: Issues found

Usage:
  python scripts/prompt_quality_de.py
  python scripts/prompt_quality_de.py --verbose
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Allow importing from the same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prompt_checks import Issue, PromptFile
from prompt_checks_crossfile import discover_prompts

# ── Constants ──────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
BUNDLED_DIR = ROOT / "packages" / "core" / "narrare_core" / "prompts" / "_bundled"

# ── Pattern Definitions (Whitelist, extendable) ───────────────

# 1. Known incorrectly split compound nouns.
#    Each entry: (regex_pattern, suggested_correction)
COMPOUND_SPLIT_PATTERNS: list[tuple[str, str]] = [
    (r"Handlungs\s+kohärenz", "Handlungskohärenz"),
    (r"Wissens\s+datenbank", "Wissensdatenbank"),
    (r"Sprech\s+weise", "Sprechweise"),
    (r"Erzähl\s+perspektive", "Erzählperspektive"),
    (r"Satz\s+struktur", "Satzstruktur"),
    (r"Wort\s+schatz", "Wortschatz"),
    (r"Schreib\s+weise", "Schreibweise"),
    (r"Sprach\s+muster", "Sprachmuster"),
    (r"Zeichen\s+beschreibung", "Zeichenbeschreibung"),
    (r"Welt\s+bau", "Weltbau"),
    (r"Erzähl\s+stimme", "Erzählstimme"),
    (r"Handlungs\s+strang", "Handlungsstrang"),
    (r"Szenen\s+übergang", "Szenenübergang"),
    (r"Dialog\s+führung", "Dialogführung"),
    (r"Charakter\s+entwicklung", "Charakterentwicklung"),
    (r"Rück\s+meldung", "Rückmeldung"),
    (r"Zusammen\s+fassung", "Zusammenfassung"),
    (r"Grund\s+lage", "Grundlage"),
    (r"Hinter\s+grund", "Hintergrund"),
    (r"Ziel\s+gruppe", "Zielgruppe"),
    (r"Beziehungs\s+gefüge", "Beziehungsgefüge"),
    (r"Schrift\s+steller", "Schriftsteller"),
    (r"Erzähl\s+ebene", "Erzählebene"),
    (r"Text\s+qualität", "Textqualität"),
    (r"Inhalt\s+struktur", "Inhaltsstruktur"),
    (r"Stil\s+mittel", "Stilmittel"),
]

# 2. Known Denglisch / unnecessary anglicisms.
#    Each entry: (regex_pattern, suggested_German_alternative)
DENGLISCH_PATTERNS: list[tuple[str, str]] = [
    (r"\balongside\b", "gemeinsam mit / zusammen mit"),
    (r"\bdeferrier(?:e|en|end)\b", "unterordnen / überlassen"),
    (r"\breviewen\b", "überarbeiten / überprüfen"),
    (r"\bfeedbacken\b", "Rückmeldung geben"),
    (r"\bcommitten\b", "einreichen / speichern"),
    (r"\bmerged\b", "zusammengeführt"),
    (r"\bge reviewed\b", "überarbeitet"),
    (r"\bReview\s*prozess\b", "Überprüfungsprozess"),
]

# ── Checks ─────────────────────────────────────────────────────


def check_compound_splitting(pf: PromptFile, issues: list[Issue]) -> None:
    """Check 1: Detect incorrectly split German compound nouns."""
    for pattern, correction in COMPOUND_SPLIT_PATTERNS:
        for match in re.finditer(pattern, pf.content, re.IGNORECASE):
            line_num = pf.content[: match.start()].count("\n") + 1
            matched_text = match.group(0)
            issues.append(
                Issue(
                    "WARN",
                    pf.display_path,
                    f"Line {line_num}: Split compound '{matched_text}' → should be '{correction}'",
                )
            )


def check_denglisch(pf: PromptFile, issues: list[Issue]) -> None:
    """Check 2: Detect Denglisch / unnecessary anglicisms."""
    for pattern, suggestion in DENGLISCH_PATTERNS:
        for match in re.finditer(pattern, pf.content, re.IGNORECASE):
            line_num = pf.content[: match.start()].count("\n") + 1
            matched_text = match.group(0)
            issues.append(
                Issue(
                    "WARN",
                    pf.display_path,
                    f"Line {line_num}: Denglisch '{matched_text}' → use '{suggestion}'",
                )
            )


# ── Reporting ──────────────────────────────────────────────────


def print_report(
    de_count: int,
    issues: list[Issue],
    verbose: bool,
) -> int:
    """Print a summary report and return exit code."""
    warns = [i for i in issues if i.level == "WARN"]
    warn_files = {i.file_path for i in warns}

    print()

    if not warns:
        print(f"CLEAN: {de_count} DE prompts checked — no quality issues found")
    else:
        print(f"FOUND: {len(warns)} quality issue(s) in {len(warn_files)} DE prompt(s)")

    for w in sorted(warns, key=lambda i: (i.file_path, i.message)):
        if verbose:
            print(f"  WARN: {w.file_path} — {w.message}")
        else:
            print(f"  WARN: {w.message}")

    print()

    if warns:
        print(f"RESULT: {len(warns)} WARN(s)")
        return 1

    print("RESULT: All DE prompts clean")
    return 0


# ── Main ───────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check DE prompt translations for quality issues.",
        epilog=("Validates DE locale files under packages/core/narrare_core/prompts/_bundled/."),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full file paths in output.",
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
        print(
            f"ERROR: Prompt directory not found: {bundled_dir}",
            file=sys.stderr,
        )
        return 1

    # Discover all prompt files, filter to DE locale only.
    all_prompts = discover_prompts(bundled_dir)
    de_prompts = [p for p in all_prompts if p.locale == "de" and p.is_system_md]

    if not de_prompts:
        print("WARN: No DE system.md prompt files found.")
        return 0

    issues: list[Issue] = []

    for pf in de_prompts:
        check_compound_splitting(pf, issues)
        check_denglisch(pf, issues)

    return print_report(len(de_prompts), issues, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
