#!/usr/bin/env python3
"""ADR filename convention gate.

Every ADR file in ``docs/architecture/decisions/`` must follow the
``ADR-XXX-short-title.md`` naming convention so that glob patterns
(``ADR-*.md``), auto-linkers and the INDEX stay consistent.

This checker is the machine enforcement for the convention that the
``_TEMPLATE.md`` and the INDEX "How to Create a New ADR" section already
declare but that was not previously enforced (review-04 AUFG-04-10 /
Strategie 5). It complements
``scripts/doc_drift/adr_checks.py::check_adr_consistency``, which keeps
its filename regex tolerant on purpose (legacy cross-references must not
break hard) — that checker validates INDEX↔file coverage, *this* checker
validates the filename shape itself.

Exit codes:
    0: All ADR files follow the convention.
    1: At least one ADR file violates the convention.

Usage:
    python scripts/check_adr_naming.py            # human-readable
    python scripts/check_adr_naming.py --json     # CI JSON output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS_DIR = ROOT / "docs" / "architecture" / "decisions"

# Files that live in the decisions directory but are intentionally not ADRs.
# These are explicitly exempt from the naming convention.
EXEMPT_BASENAMES: frozenset[str] = frozenset(
    {
        "INDEX.md",
        "_TEMPLATE.md",
    }
)

# An ADR file looks like ``ADR-XXX-short-title.md`` (three-digit, zero-padded id).
# Subdirectories (e.g. ``discussions/``) are not scanned — only top-level files.
_ADR_FILENAME_RE = re.compile(r"^ADR-(\d{3})-[a-z0-9][a-z0-9-]*\.md$")

# Anything that *looks* like an ADR attempt but is missing the prefix, so the
# checker can produce a precise "rename to …" hint instead of a generic error.
_LEGACY_ADR_RE = re.compile(r"^(?P<id>\d{3})-(?P<slug>[a-z0-9][a-z0-9-]*)\.md$")


@dataclass(frozen=True)
class NamingViolation:
    """A single ADR file that breaks the naming convention."""

    file: str
    detail: str

    def as_json(self) -> dict[str, str]:
        return asdict(self)


def _display(path: Path) -> str:
    """Return a stable display path, tolerating synthetic test paths."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.as_posix()


def _classify(path: Path) -> NamingViolation | None:
    """Return a violation if *path* breaks the convention, else ``None``."""
    name = path.name
    if name in EXEMPT_BASENAMES:
        return None
    if not name.endswith(".md"):
        # Non-markdown files are out of scope (e.g. nothing should exist, but
        # we don't want to false-positive on editor swap files either).
        return None
    if _ADR_FILENAME_RE.match(name):
        return None
    # Provide a precise rename hint for the known legacy shape
    # ``XXX-slug.md`` → ``ADR-XXX-slug.md``.
    legacy = _LEGACY_ADR_RE.match(name)
    if legacy:
        suggestion = f"ADR-{legacy['id']}-{legacy['slug']}.md"
        return NamingViolation(
            file=_display(path),
            detail=(
                f"ADR file is missing the `ADR-` prefix. "
                f"Rename to `{suggestion}`: `git mv {name} {suggestion}` "
                f"and update INDEX.md + cross-references."
            ),
        )
    return NamingViolation(
        file=_display(path),
        detail=(
            "File in docs/architecture/decisions/ does not match the "
            "`ADR-XXX-short-title.md` convention and is not in the exempt list "
            f"({sorted(EXEMPT_BASENAMES)}). Either rename to follow the "
            "convention or, if it is a non-ADR helper file, add it to "
            "`EXEMPT_BASENAMES` in scripts/check_adr_naming.py."
        ),
    )


def find_violations(decisions_dir: Path = DECISIONS_DIR) -> list[NamingViolation]:
    """Scan the decisions directory top-level and return all violations."""
    if not decisions_dir.is_dir():
        # Missing directory is out of scope for this checker; other gates own that.
        return []
    violations: list[NamingViolation] = []
    for entry in sorted(decisions_dir.iterdir()):
        if not entry.is_file():
            continue  # skip subdirectories like `discussions/`
        violation = _classify(entry)
        if violation is not None:
            violations.append(violation)
    return violations


def _print_human(violations: list[NamingViolation]) -> None:
    if not violations:
        print("✅ ADR naming convention check passed — all ADR files use `ADR-XXX-*.md`.")
        return
    print(f"❌ {len(violations)} ADR file(s) violate the naming convention:\n")
    for v in violations:
        print(f"  • {v.file}")
        print(f"    {v.detail}\n")
    print(
        "Convention: `ADR-XXX-short-title.md` (see "
        "docs/architecture/decisions/_TEMPLATE.md and INDEX.md)."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else "ADR filename convention gate"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (for CI consumption).",
    )
    parser.add_argument(
        "--decisions-dir",
        type=Path,
        default=DECISIONS_DIR,
        help="Override the decisions directory (mainly for tests).",
    )
    args = parser.parse_args(argv)

    violations = find_violations(args.decisions_dir)

    if args.json:
        payload = {
            "passed": not violations,
            "violations": [v.as_json() for v in violations],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_human(violations)

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
