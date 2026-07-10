"""Just-recipe doc-drift validator.

Prevents the recurring structural pattern where documentation references
``just <recipe>`` commands that do not exist in the justfile (review-04
AUFG-02/03/04 root cause: docs drift from the justfile recipe set).

Approach:
    1. Extract the real recipe set from ``just --list`` (justfile parse
       as fallback when ``just`` is unavailable).
    2. Scan ``docs/**/*.md`` for backtick-delimited ``just <recipe>`` refs.
    3. Report any recipe name not in the real set as a critical finding.

Exclusions:
    - Historical/archived directories (``docs/superpowers/plans/``,
      ``docs/archive/``) — point-in-time session records, not living docs.
    - Superseded/deprecated ADRs (status marker in file header) — historical
      decision records that accurately described the state at acceptance time.
    - Negation context lines (e.g. "No ``just dev-up``", "does not exist",
      "recipe to be added") — explanatory text telling readers a command
      does NOT exist.

See: docs/_shared/CONSTRAINTS.md §8 (SSOT hierarchy).
     review-04-dx-tooling.md AUFG-04-02 / AUFG-04-04.
"""

from __future__ import annotations

import re
import subprocess  # nosec B404  # controlled local just CLI invocation
from pathlib import Path

from doc_drift import safe_relative
from doc_drift.adr_checks import DocDriftFinding

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JUSTFILE = REPO_ROOT / "justfile"
_DOCS_DIR = REPO_ROOT / "docs"

# Timeout (seconds) for the `just --list` subprocess call (RULE-18: named
# constant, not a hardcoded literal in the call site).
_JUST_LIST_TIMEOUT = 10

# ── Recipe extraction ───────────────────────────────────────────

# A recipe definition in the justfile: name at column 0, optional params,
# then ':' (but not ':=' which is a ``set`` assignment).
_RECIPE_DEF_RE = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_-]*)"  # recipe name at column 0
    r"(?:\s+[^:#\n]+?)?"  # optional params (no ':' or '#' inside)
    r"\s*:(?!=)",  # defining colon, NOT followed by '=' (excludes ':=')
)

# Recipe lines from ``just --list``: leading whitespace, then name.
_LIST_RECIPE_RE = re.compile(r"^\s+([a-zA-Z_][a-zA-Z0-9_-]*)")


def _parse_justfile(justfile: Path) -> frozenset[str]:
    """Extract recipe names from the justfile text.

    Matches lines at column 0 that define a recipe (``name params: deps``).
    Excludes ``set`` directives (``:=``), comments (``#``), and indented
    recipe bodies.
    """
    try:
        content = justfile.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    recipes: set[str] = set()
    for line in content.splitlines():
        m = _RECIPE_DEF_RE.match(line)
        if m:
            recipes.add(m.group(1))
    return frozenset(recipes)


def _get_recipes_from_just_cli() -> frozenset[str] | None:
    """Get recipe names via ``just --list``.

    Returns ``None`` when ``just`` is not available (so the caller can
    fall back to justfile parsing).
    """
    try:
        result = subprocess.run(  # nosec B603 B607  # trusted local dev tool
            ["just", "--list", "--unsorted"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=_JUST_LIST_TIMEOUT,
            cwd=REPO_ROOT,
        )
    except FileNotFoundError, subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    recipes: set[str] = set()
    for line in result.stdout.splitlines():
        m = _LIST_RECIPE_RE.match(line)
        if m:
            recipes.add(m.group(1))
    return frozenset(recipes)


def get_real_recipes() -> frozenset[str]:
    """Return the authoritative recipe set.

    Prefers ``just --list`` (the authoritative runtime source); falls
    back to justfile text parsing when ``just`` is not installed.
    """
    from_cli = _get_recipes_from_just_cli()
    if from_cli is not None:
        return from_cli
    return _parse_justfile(_JUSTFILE)


# ── Doc scanning ────────────────────────────────────────────────

# Pattern to find `` `just <recipe>` `` in markdown (backtick-delimited).
_JUST_CMD_RE = re.compile(r"`just\s+([a-zA-Z_][a-zA-Z0-9_-]*)")

# Directories excluded from scanning (historical/archived content).
_EXCLUDED_DIRS: tuple[str, ...] = (
    "superpowers/plans",  # Historical session plans
    "archive",  # Archived docs
)

# Superseded/deprecated ADR status markers. Files whose first ~15 lines
# contain these markers are skipped (historical decision records).
_SUPERSEDED_MARKER_RE = re.compile(
    r"\*\*Status:\*\*\s*\S+\s+(?:Superseded|Deprecated)",
)

# Negation indicators — when present on the same line as a ``just``
# reference, the reference is explanatory (telling readers the command
# does NOT exist), not an actionable command.
_NEGATION_RE = re.compile(
    r"(?i)"
    r"(?:[Nn]o\s+`just"  # "No `just foo`"
    r"|not\s+`just"  # "not `just foo`"
    r"|without\s+`just"  # "without `just foo`"
    r"|there\s+is\s+no\s+`just"  # "there is no `just foo`"
    r"|\bdoes\s+not\s+exist\b"  # "`just foo` does not exist"
    r"|doesn.t\s+exist"  # "`just foo` doesn't exist"
    r"|\brecipe\s+to\s+be\s+added\b"  # forward reference
    r"|\bto\s+be\s+added\s+with\b"  # forward reference variant
    r")"
)


def _is_excluded_dir(rel_to_docs: Path) -> bool:
    """Check if a path (relative to docs/) falls under an excluded directory."""
    parts = rel_to_docs.parts
    for excluded in _EXCLUDED_DIRS:
        excluded_parts = tuple(excluded.split("/"))
        if parts[: len(excluded_parts)] == excluded_parts:
            return True
    return False


def _is_superseded_adr(filepath: Path) -> bool:
    """Check if an ADR file has a Superseded or Deprecated status."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError:
        return False
    # Status line is near the top; only scan the first 20 lines.
    header = "\n".join(content.splitlines()[:20])
    return bool(_SUPERSEDED_MARKER_RE.search(header))


def _scan_file(
    filepath: Path,
    real_recipes: frozenset[str],
) -> list[DocDriftFinding]:
    """Scan a single markdown file for phantom ``just`` recipe references.

    Returns a list of findings (one per phantom recipe per file).
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError:
        return []

    findings: list[DocDriftFinding] = []
    seen_phantoms: set[str] = set()

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Skip negation-context lines.
        if _NEGATION_RE.search(line):
            continue

        for m in _JUST_CMD_RE.finditer(line):
            recipe = m.group(1)
            if recipe not in real_recipes and recipe not in seen_phantoms:
                seen_phantoms.add(recipe)
                findings.append(
                    DocDriftFinding(
                        severity="critical",
                        file=safe_relative(filepath),
                        message=(
                            f"[JUST-CMD-DRIFT] Line {line_num}: references "
                            f"`just {recipe}`, which does not exist in the "
                            f"justfile recipe set. Verify the recipe name "
                            f"against `just --list` or remove the reference."
                        ),
                    )
                )
    return findings


# ── Public API ──────────────────────────────────────────────────


def check_just_command_drift(
    docs_dir: Path | None = None,
) -> list[DocDriftFinding]:
    """Run the just-recipe doc-drift check.

    Scans all ``*.md`` files under *docs_dir* (default: ``docs/``) for
    backtick-delimited ``just <recipe>`` references and reports any
    recipe name that is not in the real justfile recipe set.

    Returns an empty list when every scanned file is clean. Critical
    findings fail CI via ``check_doc_drift.py``.
    """
    effective_docs = docs_dir or _DOCS_DIR
    real_recipes = get_real_recipes()

    if not real_recipes:
        # Cannot validate without a recipe set — warn rather than crash.
        return [
            DocDriftFinding(
                severity="warning",
                file="justfile",
                message=(
                    "[JUST-CMD-DRIFT] Could not extract recipes from "
                    "`just --list` or the justfile — skipping check."
                ),
            )
        ]

    findings: list[DocDriftFinding] = []
    for md_file in sorted(effective_docs.rglob("*.md")):
        rel_to_docs = md_file.relative_to(effective_docs)

        if _is_excluded_dir(rel_to_docs):
            continue

        # Skip superseded/deprecated ADRs (historical records).
        if _is_superseded_adr(md_file):
            continue

        findings.extend(_scan_file(md_file, real_recipes))

    return findings
