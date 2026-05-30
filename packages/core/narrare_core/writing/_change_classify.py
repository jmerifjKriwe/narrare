"""Internal helpers for change_engine — change classification.

Split from ``change_engine.py`` for RULE-04 compliance (was 550 lines).
Sentence splitting and grouping extracted to :mod:`_change_grouping`.
All functions are internal (prefixed with ``_``).  Imported by
:mod:`change_engine` only.

See ADR-023 for design decisions.
"""

from __future__ import annotations

from narrare_core.writing._change_types import ChangeGroup, DiffOp

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
