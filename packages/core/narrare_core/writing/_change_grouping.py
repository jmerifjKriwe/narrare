"""Internal helpers for change_engine — sentence splitting and grouping.

Extracted from :mod:`_change_classify` for RULE-04 compliance.
All functions are internal (prefixed with ``_``).  Imported by
:mod:`change_engine` and :mod:`_change_classify`.

See ADR-023 for design decisions.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.writing._change_types import DiffOp

# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

# Regex for splitting text into sentences. Handles common abbreviations
# (Mr., Mrs., Dr., etc.) by not splitting after them.
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?…])\s+(?=[A-Z\"'\u201c\u2018])",
)

# Common abbreviations that should not trigger sentence breaks
_ABBREVIATIONS = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "sr",
        "jr",
        "st",
        "ave",
        "dept",
        "est",
        "etc",
        "vs",
        "gen",
        "col",
        "maj",
        "capt",
        "lt",
        "sgt",
        "cpl",
        "pvt",
        "repr",
        "sen",
        "gov",
        "att",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
    }
)


def _split_sentences(text: str) -> list[str]:
    """Split *text* into sentences using punctuation boundaries.

    Handles common abbreviations (Mr., Dr., etc.) to avoid false
    sentence breaks.  Returns the original text as a single-element
    list when no sentence boundary is found.
    """
    if not text:
        return []

    # Avoid false splits on short texts with abbreviations
    words = text.split()
    if len(words) < 5:
        return [text]

    # Tentative split
    candidates = _SENTENCE_SPLIT_RE.split(text)

    # Merge fragments that ended with an abbreviation
    merged: list[str] = []
    for candidate in candidates:
        if merged and _ends_with_abbreviation(merged[-1]):
            merged[-1] = merged[-1] + " " + candidate
        else:
            merged.append(candidate)

    # If no splits happened, return text as a single sentence
    if not merged or (len(merged) == 1 and merged[0] == text):
        return [text]

    return merged


def _ends_with_abbreviation(text: str) -> bool:
    """Check whether *text* ends with a known abbreviation word."""
    stripped = text.rstrip()
    last_word_match = re.search(r"(\w+)\.\s*$", stripped)
    if not last_word_match:
        return False
    return last_word_match.group(1).lower() in _ABBREVIATIONS


# ---------------------------------------------------------------------------
# Sentence boundary detection
# ---------------------------------------------------------------------------


def _find_sentence_boundaries(text: str) -> list[tuple[int, int]]:
    """Return ``(start, end)`` character offsets for each sentence in *text*."""
    if not text:
        return [(0, 0)]

    sentences = _split_sentences(text)
    boundaries: list[tuple[int, int]] = []
    pos = 0
    for sentence in sentences:
        start = text.find(sentence, pos)
        if start == -1:
            start = pos
        end = start + len(sentence)
        boundaries.append((start, end))
        pos = end
    return boundaries


# ---------------------------------------------------------------------------
# Grouping ops by sentence
# ---------------------------------------------------------------------------


def group_by_sentence(ops: list[DiffOp], original: str) -> list[list[DiffOp]]:
    """Group *ops* by the sentence in the original text they belong to.

    Returns a list of groups, where each group contains the DiffOps
    that fall within a single sentence boundary.
    """
    if not ops:
        return []

    boundaries = _find_sentence_boundaries(original)
    grouped: list[list[DiffOp]] = []
    op_index = 0

    for sent_start, sent_end in boundaries:
        group: list[DiffOp] = []
        while op_index < len(ops):
            op = ops[op_index]
            midpoint = (op.original_start + op.original_end) / 2
            if sent_start <= midpoint < sent_end:
                group.append(op)
                op_index += 1
            elif midpoint >= sent_end:
                break
            else:
                op_index += 1
        if group:
            grouped.append(group)

    # Remaining ops past all sentence boundaries
    if op_index < len(ops):
        if grouped:
            grouped[-1].extend(ops[op_index:])
        else:
            grouped.append(list(ops[op_index:]))

    return grouped
