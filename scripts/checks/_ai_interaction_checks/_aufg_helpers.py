"""Shared helpers for AUFG lifecycle checks (§6 gates 9 and 11).

Parses AUFG IDs and lifecycle states from the registry markdown and audit
evidence files. Extracted as a shared module per RULE-04 (modularize) and
RULE-06 (one responsibility: AUFG markdown parsing).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# CR-AUFG-07-XX, CR-AUFG-08-YY, AUFG-05-ZZ, etc.
_AUFG_ID_PATTERN = re.compile(r"\b((?:CR-)?AUFG-\d{2}-\d{2,3})\b")

# Registry entry header: "### CR-AUFG-07-07 — Title"
_REGISTRY_ENTRY_PATTERN = re.compile(
    r"^###\s+((?:CR-)?AUFG-\d{2}-\d{2,3})\s*[—\-]\s*(.+)$", re.MULTILINE
)

# Status line: "| Status | `open` |"
_STATUS_PATTERN = re.compile(r"\|\s*Status\s*\|\s*`(\w+)`\s*\|")

# Exit evidence block: "**Exit evidence ...:**" until next "---" or entry
_EXIT_EVIDENCE_HEADER = re.compile(r"\*\*Exit evidence[^*]*:\*\*", re.IGNORECASE)


@dataclass
class AufgEntry:
    """A parsed AUFG registry entry."""

    aufg_id: str
    title: str
    status: str
    line_number: int
    exit_evidence_text: str = ""
    implementation_files: list[str] = field(default_factory=lambda: list[str]())


def extract_aufg_ids(text: str) -> set[str]:
    """Extract all AUFG IDs (e.g. CR-AUFG-07-07, AUFG-05-09) from *text*."""
    return set(_AUFG_ID_PATTERN.findall(text))


def parse_aufg_registry(registry_path: Path) -> list[AufgEntry]:
    """Parse aufg-registry.md into structured AUFG entries.

    Extracts ID, title, status, and exit-evidence text for each entry.
    Returns an empty list if the file is missing or unreadable.
    """
    if not registry_path.exists():
        return []

    try:
        content = registry_path.read_text(encoding="utf-8")
    except OSError:
        return []

    entries: list[AufgEntry] = []
    lines = content.splitlines()

    for match in _REGISTRY_ENTRY_PATTERN.finditer(content):
        aufg_id = match.group(1)
        title = match.group(2).strip()
        # line_number is 1-indexed
        line_number = content[: match.start()].count("\n") + 1

        # Find the section for this entry: from header line to next "### " or "---"
        section_start = match.start()
        remaining_headers = list(_REGISTRY_ENTRY_PATTERN.finditer(content, match.end()))
        section_end = remaining_headers[0].start() if remaining_headers else len(content)
        # Also check for "---" separator before next header
        separator = content.find("\n---\n", match.end())
        if separator != -1 and (section_end == len(content) or separator < section_end):
            section_end = separator

        section_text = content[section_start:section_end]

        status_match = _STATUS_PATTERN.search(section_text)
        status = status_match.group(1) if status_match else "unknown"

        exit_text = ""
        exit_match = _EXIT_EVIDENCE_HEADER.search(section_text)
        if exit_match:
            exit_start = exit_match.end()
            exit_text = section_text[exit_start : exit_start + 2000].strip()
            # Truncate at next "**" bold header or "---"
            for delimiter in ("\n---\n", "\n\n---\n", "**Acceptance", "**Definition"):
                cut = exit_text.find(delimiter)
                if cut != -1:
                    exit_text = exit_text[:cut].strip()

        # Extract file paths from exit evidence (code + governance docs).
        impl_files = re.findall(
            r"[a-z_./\-]+\.(?:py|ts|tsx|js|jsx|yaml|yml|json|toml|md)",
            exit_text,
        )

        entries.append(
            AufgEntry(
                aufg_id=aufg_id,
                title=title,
                status=status,
                line_number=line_number,
                exit_evidence_text=exit_text,
                implementation_files=impl_files,
            )
        )

    _ = lines  # kept for potential future line-level diagnostics
    return entries


def get_registry_ids(entries: list[AufgEntry]) -> set[str]:
    """Return the set of all AUFG IDs present in parsed registry entries."""
    return {e.aufg_id for e in entries}
