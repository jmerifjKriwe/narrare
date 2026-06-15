"""Parser for the AUFG lifecycle registry (``aufg-registry.md``).

Single responsibility (RULE-06): read the registry markdown and return
structured entries. This module does NOT import application runtime
internals (RULE-07) — it only parses a markdown file.

Registry entry format::

    ### AUFG-05-07 — Title Here

    | Field | Value |
    |-------|-------|
    | ID | AUFG-05-07 |
    | Status | `resolved` |

    ...

Accepted-risk entries use ``| Type | `accepted_risk` |`` instead of
``| Status | ... |``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

#: Matches a markdown header that starts an AUFG/AR/AE entry.
#:   ``### AUFG-05-07 — CORS Audit``
_ENTRY_HEADER_RE = re.compile(
    r"^(#{1,6})\s+"
    r"(AUFG|AR|AE)-(\d{2})-(\d{2})"
    r"\s*[—–-]\s*"  # noqa: RUF001 — em/en dash intentionally matched
    r"(.+)$",
    re.MULTILINE,
)

#: Matches a ``| Status | `value` |`` table row.
_STATUS_ROW_RE = re.compile(
    r"^\|\s*Status\s*\|\s*`?([^|`]+?)`?\s*\|\s*$",
    re.MULTILINE,
)

#: Matches a ``| Type | `value` |`` table row (accepted risks).
_TYPE_ROW_RE = re.compile(
    r"^\|\s*Type\s*\|\s*`?([^|`]+?)`?\s*\|\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class AufgEntry:
    """A single lifecycle entry from the AUFG registry."""

    entry_id: str
    title: str
    status: str


@dataclass(frozen=True)
class AufgRegistry:
    """Parsed registry with lookup helpers."""

    entries: dict[str, AufgEntry]

    def get(self, entry_id: str) -> AufgEntry | None:
        """Return the entry for *entry_id*, or ``None`` if absent."""
        return self.entries.get(entry_id)

    def has(self, entry_id: str) -> bool:
        """Return ``True`` if *entry_id* is present in the registry."""
        return entry_id in self.entries


def _normalize_status(raw: str) -> str:
    """Strip backticks and surrounding whitespace from a status value."""
    return raw.strip().strip("`").strip()


def _find_section_text(text: str, start: int) -> str:
    """Return the text between *start* and the next header of any level."""
    next_h2 = text.find("\n## ", start)
    next_h3 = text.find("\n### ", start)
    candidates = [end for end in (next_h2, next_h3) if end != -1]
    end = min(candidates) if candidates else len(text)
    return text[start:end]


def _extract_status(section_text: str) -> str:
    """Extract the lifecycle status from an entry's table section."""
    status_match = _STATUS_ROW_RE.search(section_text)
    if status_match:
        return _normalize_status(status_match.group(1))
    type_match = _TYPE_ROW_RE.search(section_text)
    if type_match:
        return _normalize_status(type_match.group(1))
    return "unknown"


def parse_registry(text: str) -> AufgRegistry:
    """Parse registry markdown *text* into an :class:`AufgRegistry`."""
    entries: dict[str, AufgEntry] = {}
    for match in _ENTRY_HEADER_RE.finditer(text):
        prefix = match.group(2)
        entry_id = f"{prefix}-{match.group(3)}-{match.group(4)}"
        title = match.group(5).strip()
        section = _find_section_text(text, match.end())
        status = _extract_status(section)
        entries[entry_id] = AufgEntry(
            entry_id=entry_id,
            title=title,
            status=status,
        )
    return AufgRegistry(entries=entries)


def load_registry(path: Path) -> AufgRegistry:
    """Read and parse the registry file at *path*."""
    return parse_registry(path.read_text(encoding="utf-8"))
