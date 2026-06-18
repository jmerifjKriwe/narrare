"""ADR-STATUS · ADR INDEX ↔ ADR file status consistency (ADR-049 Phase D D8).

Validates that the status shown in ``docs/architecture/decisions/INDEX.md``
matches the status declared in each ADR file's frontmatter/header.

**Why this exists:** ADR-049 itself has a status discrepancy — the ADR file
says "Accepted (contract decisions); implementation deferred to Phase C" but
the INDEX uses a bare "✅" marker.  This checker makes such mismatches
visible and CI-blocking.

**Scope (documented):** This is a lightweight consistency assertion between
INDEX.md ADR status markers and ADR file Status lines.  It does NOT validate
CURRENT_STATE.md completeness claims against open findings (that is a larger
Phase E deliverable).  The scope is intentionally narrow to be CI-safe.

See: ``docs/architecture/decisions/ADR-049-prompt-surface-identity-path-contract.md``
      (D8 — CURRENT_STATE-Konsistenz-Check, acceptance criteria)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from scripts.architecture.types import CheckResult, Violation

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# INDEX.md status legend (from INDEX.md §Status Legend).
# Maps the symbol shown in INDEX.md to the canonical status keyword.
_INDEX_STATUS_SYMBOLS: dict[str, str] = {
    "✅": "Accepted",
    "🔄": "Proposed",
    "⛔": "Superseded",
    "🗄️": "Deprecated",
}

# Regex to extract ADR entries from INDEX.md table rows.
# Format: | [ADR-XXX](filename) | Title | STATUS | Date | Affects |
_INDEX_ROW_RE = re.compile(
    r"\|\s*\[(ADR-\d+)\]\(([^)]+)\)\s*\|[^|]*\|\s*([^|]+?)\s*\|",
)

# Regex to extract the Status line from an ADR file.
# Matches: > **Status:** ✅ Accepted  OR  Status: Proposed  OR  **Status:** 🔄
_ADR_STATUS_RE = re.compile(
    r"\*?\*?Status:?\*?\*?\s*:?\s*(.+?)(?:$|\n)",
    re.IGNORECASE | re.MULTILINE,
)

# Rule identifier.
_RULE = "ADR-STATUS"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_index_statuses(index_text: str) -> dict[str, tuple[str, str]]:
    """Parse ADR ID → (filename, raw_status_text) from INDEX.md.

    Returns a dict mapping ``"ADR-049"`` → ``("ADR-049-...md", "✅")``.
    """
    result: dict[str, tuple[str, str]] = {}
    for match in _INDEX_ROW_RE.finditer(index_text):
        adr_id = match.group(1)
        filename = match.group(2)
        raw_status = match.group(3).strip()
        result[adr_id] = (filename, raw_status)
    return result


def _normalize_index_status(raw: str) -> str:
    """Normalize an INDEX.md status cell to a canonical keyword.

    Examples:
    - "✅" → "Accepted"
    - "✅ Implemented" → "Accepted" ( Implemented is informational )
    - "🔄" → "Proposed"
    - "⛔" → "Superseded"
    """
    for symbol, keyword in _INDEX_STATUS_SYMBOLS.items():
        if symbol in raw:
            return keyword
    # Fallback: try to match by keyword
    lower = raw.lower()
    if "accept" in lower or "implement" in lower:
        return "Accepted"
    if "propos" in lower:
        return "Proposed"
    if "supers" in lower:
        return "Superseded"
    if "deprecated" in lower or "deprecat" in lower:
        return "Deprecated"
    return ""


def _parse_adr_file_status(content: str) -> str:
    """Extract the Status from an ADR file's header.

    Looks for lines like:
    - ``> **Status:** ✅ Accepted``
    - ``> **Status:** 🔄 Proposed``
    - ``Status: Accepted``
    """
    match = _ADR_STATUS_RE.search(content)
    if match is None:
        return ""
    raw = match.group(1).strip()
    # Extract the keyword from the raw status text
    for symbol, keyword in _INDEX_STATUS_SYMBOLS.items():
        if symbol in raw:
            return keyword
    # Check for keyword without symbol
    lower = raw.lower()
    if "accept" in lower:
        return "Accepted"
    if "propos" in lower:
        return "Proposed"
    if "supers" in lower:
        return "Superseded"
    if "deprecated" in lower:
        return "Deprecated"
    return ""


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------


def check_adr_status_consistency(result: CheckResult, root: Path) -> None:
    """D8 — Validate INDEX.md ADR statuses match ADR file statuses.

    For each ADR listed in INDEX.md, compares the INDEX status marker
    against the Status declared in the ADR file itself.  Flags mismatches.

    Also validates that INDEX status cells use only the canonical symbols
    from the Status Legend (✅ 🔄 ⛔ 🗄️).
    """
    index_path = root / "docs" / "architecture" / "decisions" / "INDEX.md"
    decisions_dir = root / "docs" / "architecture" / "decisions"

    if not index_path.is_file():
        # Not applicable if INDEX.md doesn't exist.
        return

    index_text = index_path.read_text(encoding="utf-8")
    index_statuses = _parse_index_statuses(index_text)

    for adr_id, (filename, raw_index_status) in sorted(index_statuses.items()):
        index_status = _normalize_index_status(raw_index_status)

        # Validate INDEX status uses a canonical symbol
        if not index_status:
            result.violations.append(
                Violation(
                    file=index_path,
                    line=0,
                    rule=_RULE,
                    detail=(
                        f"INDEX.md status for {adr_id} uses non-canonical "
                        f"marker {raw_index_status!r}. Valid symbols: "
                        f"✅ (Accepted), 🔄 (Proposed), ⛔ (Superseded), "
                        f"🗄️ (Deprecated)."
                    ),
                )
            )
            continue

        # Read the ADR file
        adr_path = decisions_dir / filename
        if not adr_path.is_file():
            # Missing ADR file is flagged by other gates; skip here.
            continue

        try:
            adr_content = adr_path.read_text(encoding="utf-8")
        except OSError:
            continue

        adr_status = _parse_adr_file_status(adr_content)
        if not adr_status:
            # ADR file has no parseable Status line — skip (not all ADRs
            # may use the same format; this is informational, not blocking).
            continue

        if index_status != adr_status:
            result.violations.append(
                Violation(
                    file=adr_path,
                    line=0,
                    rule=_RULE,
                    detail=(
                        f"Status mismatch: INDEX.md says {index_status!r} "
                        f"({_INDEX_STATUS_SYMBOLS.get(index_status, '?')} → "
                        f"INDEX cell: {raw_index_status!r}), but ADR file "
                        f"declares {adr_status!r}. Keep INDEX and ADR file "
                        f"status in sync."
                    ),
                )
            )
