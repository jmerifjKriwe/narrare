"""Candidate-finding extractor for technical-review files.

Single responsibility (RULE-06): scan ``review-*.md`` prose and identify
candidate findings that may need AUFG / accepted-risk / accepted-enhancement
lifecycle coverage. This module reads files only (RULE-07).

Finding sections are identified by headers or bold labels containing
``Offene Punkte`` or ``Schwächen``. Within those sections, bullet items
(``-``/``*``) and numbered items (``1.``) are collected as candidates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

#: Patterns matching lines that start a finding section.
_FINDING_SECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^#{1,6}\s+Offene\s+Punkte", re.IGNORECASE),
    re.compile(r"^#{1,6}\s+Schw[aä]chen", re.IGNORECASE),
    re.compile(r"^\*\*\s*Offene\s+Punkte", re.IGNORECASE),
    re.compile(r"^\*\*\s*Schw[aä]chen", re.IGNORECASE),
)

#: Matches a bullet or numbered list item.
_ITEM_RE = re.compile(r"^(?:[-*]\s+|\d+\.\s+)(.+)$")

#: Matches a continuation line (indented, not a new item).
_CONTINUATION_RE = re.compile(r"^[ \t]+\S")

#: Matches any markdown header.
_HEADER_RE = re.compile(r"^#{1,6}\s")

#: Matches a horizontal rule.
_HR_RE = re.compile(r"^---+\s*$")

#: Matches lifecycle IDs: AUFG-XX-YY, AR-XX-YY, AE-XX-YY.
_REFERENCE_RE = re.compile(r"\b(AUFG|AR|AE)-(\d{2})-(\d{2})\b")


@dataclass(frozen=True)
class CandidateFinding:
    """A candidate finding extracted from a review file."""

    source_file: str
    line_number: int
    text: str
    references: tuple[str, ...]


def extract_references(text: str) -> tuple[str, ...]:
    """Return unique lifecycle IDs found in *text*, preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for prefix, n1, n2 in _REFERENCE_RE.findall(text):
        ref = f"{prefix}-{n1}-{n2}"
        if ref not in seen:
            seen.add(ref)
            result.append(ref)
    return tuple(result)


def _is_finding_section_header(line: str) -> bool:
    """Return ``True`` if *line* starts a finding section."""
    return any(pattern.match(line) for pattern in _FINDING_SECTION_PATTERNS)


def _collect_item(lines: list[str], start: int) -> tuple[str, int]:
    """Join a list item at *start* with its continuation lines.

    Returns ``(joined_text, next_index)``.
    """
    match = _ITEM_RE.match(lines[start])
    assert match is not None  # caller guarantees this
    parts: list[str] = [match.group(1).strip()]
    idx = start + 1
    while idx < len(lines):
        line = lines[idx]
        if _CONTINUATION_RE.match(line) and not _ITEM_RE.match(line):
            parts.append(line.strip())
            idx += 1
        else:
            break
    return " ".join(parts), idx


def extract_candidate_findings(text: str, source_file: str) -> list[CandidateFinding]:
    """Extract candidate findings from review markdown *text*.

    *source_file* is the filename used in the returned findings for reporting.
    """
    lines = text.splitlines()
    findings: list[CandidateFinding] = []
    in_section = False
    idx = 0

    while idx < len(lines):
        line = lines[idx]

        if _is_finding_section_header(line):
            in_section = True
            idx += 1
            continue

        if _HEADER_RE.match(line):
            in_section = False
            idx += 1
            continue

        if _HR_RE.match(line.strip()):
            in_section = False
            idx += 1
            continue

        if in_section and _ITEM_RE.match(line):
            joined, next_idx = _collect_item(lines, idx)
            findings.append(
                CandidateFinding(
                    source_file=source_file,
                    line_number=idx + 1,
                    text=joined,
                    references=extract_references(joined),
                )
            )
            idx = next_idx
            continue

        idx += 1

    return findings


def load_findings(
    review_dir: Path,
    pattern: str = "review-*.md",
) -> list[CandidateFinding]:
    """Load and extract findings from all review files in *review_dir*."""
    findings: list[CandidateFinding] = []
    for path in sorted(review_dir.glob(pattern)):
        text = path.read_text(encoding="utf-8")
        findings.extend(extract_candidate_findings(text, path.name))
    return findings
