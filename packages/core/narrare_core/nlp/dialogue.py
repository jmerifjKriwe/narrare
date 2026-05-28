"""
Dialogue extraction — finds quoted speech in prose text.

Uses regex patterns to detect:
- ``"double quotes"`` (English)
- ``'single quotes'`` (English narrative)
- ``»guillemets«`` (German / Swiss)
- ``«guillemets à la française»`` (French)
- Em-dash interruptions (—)

This module has **no spaCy dependency** — it is pure regex and can
be used even when ``SpacyNLPProvider.is_available()`` returns ``False``.

Used by:
- ANAL-002: to separate dialogue from narration in sentiment analysis.
- ANAL-007/008: voice metrics (dialogue ratio).
- ANAL-004: POV detection (character voice attribution).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class DialogueLine:
    """A single piece of quoted speech extracted from text.

    Attributes:
        text: The content inside the quotation marks (unquoted).
        speaker: The detected speaker name, or ``None`` if unknown.
        start: Character offset of the opening quote in the source text.
        end: Character offset right after the closing quote (exclusive).
    """

    text: str
    speaker: str | None = None
    start: int = 0
    end: int = 0


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# English double quotes: "Hello," she said.
_PAT_DOUBLE = re.compile(r'"([^"]*)"')

# English single quotes: 'Hello,' she said.
_PAT_SINGLE = re.compile(r"'([^']*)'")

# German/French guillemets: »Guten Tag«
_PAT_GUILLEMET = re.compile(r"»([^»]*)«")

# French guillemets: «Bonjour»
_PAT_FR_GUILLEMET = re.compile(r"«([^»]*)»")

# Combined order: most specific → least specific
_QUOTE_PATTERNS: list[re.Pattern[str]] = [
    _PAT_DOUBLE,
    _PAT_SINGLE,
    _PAT_GUILLEMET,
    _PAT_FR_GUILLEMET,
]

# Speaker attribution patterns (before or after a quote)
# Matches: "text," he said. / She said, "text." / "text," whispered Mary.
_SPEAKER_PATTERNS: list[re.Pattern[str]] = [
    # "Quote," he said. / "Quote," said John.
    re.compile(
        r"(?:said|asked|replied|answered|whispered|shouted|yelled|"
        r"murmured|muttered|screamed|cried|called|breathed|thought|"
        r"wondered|continued|added|interrupted|whined|exclaimed|"
        r"snarled|snapped|hissed|growled|roared|sobbed|laughed|"
        r"chuckled|whimpered|rasped|drawled|echoed|sang)\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ),
    # She said, "quote." He replied, "quote."
    re.compile(
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:said|asked|replied|"
        r"answered|whispered|shouted|yelled|murmured|muttered|"
        r"screamed|cried|called|breathed|thought|wondered|continued|"
        r"added|interrupted|whined|exclaimed|snarled|snapped|hissed|"
        r"growled|roared|sobbed|laughed|chuckled|whimpered|rasped|"
        r"drawled|echoed|sang)",
    ),
]

# Em-dash interruption: "I was going to say—" she interrupted.
_PAT_EMDASH_INTERRUPTION = re.compile(r'—[^—"]*"')

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_dialogue(text: str) -> list[DialogueLine]:
    """Extract all quoted speech from *text*.

    Finds text enclosed in double quotes (``"..."``), single quotes
    (``'...'``), German guillemets (``»...«``), and French guillemets
    (``«...»``).  Attempts to detect the speaker by scanning for
    attribution verbs (said, asked, whispered, etc.) around each quote.

    Args:
        text: The prose text to analyse.

    Returns:
        List of :class:`DialogueLine` objects, in order of appearance.
    """
    results: list[DialogueLine] = []

    # Collect all quote spans from all patterns
    spans: list[tuple[int, int, str, str]] = []  # (start, end, content, pattern_tag)

    for pattern in _QUOTE_PATTERNS:
        for match in pattern.finditer(text):
            content = match.group(1)
            start = match.start()
            end = match.end()
            # Avoid double-counting nested quotes (e.g., ' "nested" ')
            # by checking if this span overlaps an already-found one
            if not _overlaps_any(start, end, spans):
                spans.append((start, end, content, "quote"))

    # Sort by start position
    spans.sort(key=lambda s: s[0])

    for start, end, content, _ in spans:
        # Try to detect speaker from surrounding context
        # Look at text before and after the quote
        before = text[max(0, start - 150) : start]
        after = text[end : min(len(text), end + 150)]

        speaker = _detect_speaker(before, after)

        results.append(
            DialogueLine(
                text=content,
                speaker=speaker,
                start=start,
                end=end,
            )
        )

    return results


def is_dialogue_line(line: str) -> bool:
    """Check whether a text line contains quoted speech.

    Args:
        line: A single line of text.

    Returns:
        ``True`` if *line* contains any matched quote characters.
    """
    return any(pattern.search(line) for pattern in _QUOTE_PATTERNS)


def count_dialogue_ratio(text: str) -> float:
    """Compute the ratio of dialogue characters to total characters.

    Counts all characters inside quotation marks (excluding the marks
    themselves) and divides by the total text length.

    Args:
        text: The prose text to analyse.

    Returns:
        A float between ``0.0`` (no dialogue) and ``1.0`` (all dialogue).
        Returns ``0.0`` for empty text.
    """
    if not text or not text.strip():
        return 0.0

    total_dialogue_chars = 0

    for pattern in _QUOTE_PATTERNS:
        for match in pattern.finditer(text):
            total_dialogue_chars += len(match.group(1))

    return total_dialogue_chars / len(text)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _detect_speaker(before: str, after: str) -> str | None:
    """Try to identify the speaker from context around a quote.

    Args:
        before: Text immediately before the quoted passage.
        after: Text immediately after the quoted passage.

    Returns:
        Detected speaker name, or ``None``.
    """
    # Check "before" context: "quote," she said → speaker before quote
    for pattern in _SPEAKER_PATTERNS:
        # Look in both directions
        match_before = pattern.search(before)
        if match_before:
            # The named group is always the last group
            speaker = match_before.lastgroup
            if speaker:
                name = match_before.group(speaker)
            else:
                groups = [g for g in match_before.groups() if g is not None]
                name = groups[-1] if groups else None
            if name:
                return name

        match_after = pattern.search(after)
        if match_after:
            speaker = match_after.lastgroup
            if speaker:
                name = match_after.group(speaker)
            else:
                groups = [g for g in match_after.groups() if g is not None]
                name = groups[-1] if groups else None
            if name:
                return name

    return None


def _overlaps_any(
    start: int,
    end: int,
    existing: list[tuple[int, int, str, str]],
) -> bool:
    """Check whether a span overlaps any existing span."""
    return any(start < ex_end and end > ex_start for ex_start, ex_end, _, _ in existing)
