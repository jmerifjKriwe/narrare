"""Registry-section parsing for the review→registry linking checker.

Single responsibility (RULE-06 / RULE-04 extraction): turn registry markdown into
the set of AUFG ids each ``### `` section covers. Split out of
:mod:`governance._review_registry_link` so the linking checker stays under the
script file-size limit.

A registry section is delimited by a ``### `` header. Three header shapes carry
ids, all parsed here:

  * a single-id entry header ``### AUFG-01-01 — Title`` (``_ENTRY_HEADER_RE``);
  * a range-id set header ``### CR-AUFG-01-01..06 — Title`` (the id range in
    the header itself — ``_ENTRY_RANGE_HEADER_RE``); and
  * a set header whose title carries no parseable id, with the ids declared in
    a ``| IDs | … through … |`` row inside the section (the CR-08 set —
    ``_IDS_RANGE_ROW_RE``).

A section covering many ids (range header or range row) is expanded into one id
per entry so a per-id review header is not falsely flagged missing.

RULE-07: reads registry markdown only. Imports no application runtime modules.

ADR: docs/architecture/decisions/ADR-062-governance-drift-phase2-status-ssot.md
"""

from __future__ import annotations

import re

__all__ = [
    "ENTRY_HEADER_RE",
    "ENTRY_RANGE_HEADER_RE",
    "IDS_RANGE_ROW_RE",
    "expand_range_header",
    "expand_range_ids",
    "ids_row_list",
    "iter_registry_sections",
    "section_ids",
]

#: Matches a registry entry header: ``### AUFG-01-01 — Title``.
ENTRY_HEADER_RE = re.compile(
    r"^(#{1,6})\s+((?:CR-)?(?:AUFG|AR|AE))-(\d{2})-(\d{2})\s*[—–-]\s*(.+)$",  # noqa: RUF001
    re.MULTILINE,
)

#: Matches a registry set-block header whose id is itself a range:
#: ``### CR-AUFG-01-01..06 — Title``. Captures prefix, NN, start MM, end MM.
ENTRY_RANGE_HEADER_RE = re.compile(
    r"^#{1,6}\s+((?:CR-)?(?:AUFG|AR|AE))-(\d{2})-(\d{2})\.\.(\d{2})\s*[—–-]?",  # noqa: RUF001
)

#: Matches a range-form ``| IDs | <prefix>-(\d{2})-(\d{2}) through <prefix>-(\d{2})-(\d{2}) |``
#: row (the CR-08 set). Used to expand a single registry section into per-id
#: keys so a per-id header is not falsely flagged missing.
IDS_RANGE_ROW_RE = re.compile(
    r"^\|\s*IDs\s*\|\s*"
    r"(?P<prefix>(?:CR-)?(?:AUFG|AR|AE))-(?P<nn>\d{2})-(?P<start>\d{2})"
    r"\s+through\s+"
    r"(?P<end_prefix>(?:CR-)?(?:AUFG|AR|AE))-(?P<end_nn>\d{2})-(?P<end>\d{2})"
    r"\s*\|\s*$",
    re.MULTILINE,
)


def iter_registry_sections(text: str) -> list[str]:
    """Yield the body text of each ``### `` section in registry markdown.

    Each returned section *includes* its header line so id-extraction can read
    both the header and any ``| IDs |`` row. Sections end at the next ``### `` or
    ``## `` header.
    """
    lines = text.splitlines()
    sections: list[str] = []
    current: list[str] = []
    for line in lines:
        is_h3 = line.startswith("### ")
        is_h2 = line.startswith("## ")
        if is_h3 or is_h2:
            if current:
                sections.append("\n".join(current))
                current = []
            if is_h3:
                current = [line]
            # h2 ends the section without starting a new one
        elif current:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    return sections


def section_ids(section_text: str) -> list[str]:
    """Return all registry ids a section covers (header id + range expansions).

    Sources, in priority order: an ``| IDs | … through … |`` row (canonical for
    set blocks), a range-id header (``### CR-AUFG-01-01..06``), or a single-id
    header (``### AUFG-01-01``). Comma-separated ``| IDs |`` lists are also
    parsed so a section need not use the ``through`` form.
    """
    ids: list[str] = []
    seen: set[str] = set()

    # 1. Range row: "| IDs | PREFIX-NN-01 through PREFIX-NN-14 |"
    for ranged_id in expand_range_ids(section_text):
        if ranged_id not in seen:
            seen.add(ranged_id)
            ids.append(ranged_id)
    if ids:
        return ids

    # 2. Comma-list row: "| IDs | CR-AUFG-01-01, CR-AUFG-01-02 |"
    for listed_id in ids_row_list(section_text):
        if listed_id not in seen:
            seen.add(listed_id)
            ids.append(listed_id)

    # 3. Range-id header: "### CR-AUFG-01-01..06"
    header_line = section_text.splitlines()[0] if section_text else ""
    for ranged_id in expand_range_header(header_line):
        if ranged_id not in seen:
            seen.add(ranged_id)
            ids.append(ranged_id)

    # 4. Single-id header: "### AUFG-01-01 — Title"
    if not ids:
        match = ENTRY_HEADER_RE.search(header_line)
        if match:
            single = f"{match.group(2)}-{match.group(3)}-{match.group(4)}"
            ids.append(single)
    return ids


def ids_row_list(section_text: str) -> list[str]:
    """Parse a comma-separated ``| IDs | CR-AUFG-01-01, … |`` row."""
    match = re.search(r"^\|\s*IDs\s*\|\s*(.+?)\s*\|\s*$", section_text, re.MULTILINE)
    if match is None:
        return []
    ids: list[str] = []
    for token in match.group(1).split(","):
        token = token.strip()
        m = re.match(r"^((?:CR-)?(?:AUFG|AR|AE))-(\d{2})-(\d{2})$", token)
        if m:
            ids.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    return ids


def expand_range_header(header_line: str) -> list[str]:
    """Expand a ``### CR-AUFG-01-01..06 — Title`` range-id header to per-id keys."""
    match = ENTRY_RANGE_HEADER_RE.match(header_line)
    if match is None:
        return []
    prefix, nn, start, end = match.group(1), match.group(2), match.group(3), match.group(4)
    try:
        s, e = int(start), int(end)
    except TypeError, ValueError:
        return []
    if e < s:
        return []
    return [f"{prefix}-{nn}-{mm:02d}" for mm in range(s, e + 1)]


def expand_range_ids(section_text: str) -> list[str]:
    """Expand a ``| IDs | PREFIX-NN-01 through PREFIX-NN-14 |`` row to per-id keys.

    Returns an empty list when the section has no range row, or when the range is
    degenerate (end < start). Only same-NN ranges are expanded — a cross-NN range
    (e.g. 01-09 through 02-01) is left unexpanded to avoid surprising sweeps.
    """
    match = IDS_RANGE_ROW_RE.search(section_text)
    if match is None:
        return []
    nn = match.group("nn")
    if nn != match.group("end_nn"):
        return []
    try:
        start = int(match.group("start"))
        end = int(match.group("end"))
    except TypeError, ValueError:
        return []
    if end < start:
        return []
    prefix = match.group("prefix")
    return [f"{prefix}-{nn}-{mm:02d}" for mm in range(start, end + 1)]
