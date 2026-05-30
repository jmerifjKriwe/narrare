"""Internal helpers for change_engine — sentence splitting, grouping, classification.

Split from ``change_engine.py`` for RULE-04 compliance (was 550 lines).
All functions are internal (prefixed with ``_``).  Imported by
:mod:`change_engine` only.

See ADR-023 for design decisions.
"""

from __future__ import annotations

import re

from narrare_core.writing._change_types import ChangeGroup, DiffOp

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


# ---------------------------------------------------------------------------
# Building ChangeGroup instances
# ---------------------------------------------------------------------------


def _build_change_group(
    ops: list[DiffOp],
    original: str,
    revised: str,
    change_type: str,
    index: int,
) -> ChangeGroup:
    """Build a :class:`ChangeGroup` from a list of related *ops*.

    Computes the full original and revised text spans for the group
    by expanding to the nearest sentence boundaries, so that
    classification can examine context (e.g. quotation marks that
    may appear in "equal" diff ops).
    """
    if not ops:
        return ChangeGroup(
            original_text="",
            revised_text="",
            ops=[],
            change_type=change_type,
            index=index,
        )

    # Union of original character ranges → expand to sentence
    orig_start = min(op.original_start for op in ops)
    orig_end = max(op.original_end for op in ops)
    sent_orig_start, sent_orig_end = _expand_to_sentence(orig_start, orig_end, original)

    # Union of revised character ranges → expand to sentence
    rev_start = min(op.revised_start for op in ops)
    rev_end = max(op.revised_end for op in ops)
    sent_rev_start, sent_rev_end = _expand_to_sentence(rev_start, rev_end, revised)

    return ChangeGroup(
        original_text=original[sent_orig_start:sent_orig_end],
        revised_text=revised[sent_rev_start:sent_rev_end],
        ops=list(ops),
        change_type=change_type,
        index=index,
    )


def _expand_to_sentence(start: int, end: int, text: str) -> tuple[int, int]:
    """Expand *(start, end)* outward to include the full sentence.

    Walks outward to find sentence boundaries (``.``, ``!``, ``?``, ``…``)
    and expands the range to include the entire containing sentence.
    """
    if not text:
        return (start, end)

    length = len(text)

    # Expand backward to start of sentence
    new_start = start
    while new_start > 0:
        new_start -= 1
        if text[new_start] in ".!?…\n":
            new_start += 1
            break
    else:
        new_start = 0

    # Expand forward to end of sentence
    new_end = end
    while new_end < length:
        if text[new_end] in ".!?…\n":
            new_end += 1
            break
        new_end += 1
    else:
        new_end = length

    return (new_start, new_end)


# ---------------------------------------------------------------------------
# Change classification
# ---------------------------------------------------------------------------


def classify_groups(
    group_lists: list[list[DiffOp]],
    focus_areas: list[str],
    original: str,
    revised: str,
) -> list[ChangeGroup]:
    """Classify grouped diff ops into typed :class:`ChangeGroup` instances.

    Classification rules:
    1. One focus area → all groups get that type.
    2. ``"dialogue"`` in focus → groups with quotation marks → ``"dialogue"``.
    3. ``"description"`` in focus → groups without quotes → ``"description"``.
    4. Fallback: ``"word_choice"`` vs ``"sentence"`` by magnitude.
    """
    if not group_lists:
        return []

    # Build groups first (need full text spans for classification)
    built: list[ChangeGroup] = [
        _build_change_group(ops, original, revised, "", idx) for idx, ops in enumerate(group_lists)
    ]

    # Single focus area — uniform classification
    if len(focus_areas) == 1:
        single = focus_areas[0]
        return [
            ChangeGroup(
                original_text=g.original_text,
                revised_text=g.revised_text,
                ops=g.ops,
                change_type=single,
                index=g.index,
            )
            for g in built
        ]

    result: list[ChangeGroup] = []
    for g in built:
        ctype = _classify_single_group(g, focus_areas)
        result.append(
            ChangeGroup(
                original_text=g.original_text,
                revised_text=g.revised_text,
                ops=g.ops,
                change_type=ctype,
                index=g.index,
            )
        )
    return result


def _classify_single_group(group: ChangeGroup, focus_areas: list[str]) -> str:
    """Determine the change type for a single change *group*.

    Examines the group's full original text span (including context
    like quotation marks that may be in ``"equal"`` diff ops).
    """
    orig_text = group.original_text

    if "dialogue" in focus_areas and _contains_quotes(orig_text):
        return "dialogue"

    if "description" in focus_areas and not _contains_quotes(orig_text):
        return "description"

    if _is_single_word_change(group.ops) and "word_choice" in focus_areas:
        return "word_choice"

    if "sentence" in focus_areas:
        return "sentence"

    # Fallback: magnitude-based
    return "word_choice" if len(orig_text.split()) <= 3 else "sentence"


def _contains_quotes(text: str) -> bool:
    """Check whether *text* contains dialogue quotation marks."""
    return any(c in text for c in {'"', "'", "\u201c", "\u201d", "\u2018", "\u2019"})


def _is_single_word_change(ops: list[DiffOp]) -> bool:
    """Check whether the changes in *ops* affect only a single word."""
    if len(ops) == 1 and ops[0].type == "replace":
        return len(ops[0].content_original.strip().split()) <= 1
    combined = "".join(op.content_original for op in ops).strip()
    return len(combined.split()) <= 1
