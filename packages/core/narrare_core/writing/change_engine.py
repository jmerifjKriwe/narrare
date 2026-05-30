"""Change engine — server-side diff computation for co-author mode.

Pure-function module for computing diffs between original and revised text.
No I/O, no side effects, no LLM calls. Deterministic and testable.

Uses :func:`difflib.SequenceMatcher` for the base diff, then groups
individual operations by sentence boundary and classifies them based on
user-selected focus areas.  Grouping and classification logic lives in
:mod:`_change_classify`.

See ADR-023 for design decisions.

Usage::

    result = compute_changes(original, revised, focus_areas=["dialogue"])
    if result.has_changes:
        for group in result.changes:
            print(group.change_type, group.original_text, group.revised_text)
"""

from __future__ import annotations

import difflib

from narrare_core.writing._change_classify import (
    classify_groups,
    group_by_sentence,
)
from narrare_core.writing._change_types import DiffOp, DiffResult

__all__: list[str] = [
    "ChangeGroup",
    "DiffOp",
    "DiffResult",
    "compute_changes",
    "has_meaningful_changes",
]

# Re-export types for convenience
from narrare_core.writing._change_types import ChangeGroup

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_changes(
    original: str,
    revised: str,
    focus_areas: list[str] | None = None,
) -> DiffResult:
    """Compute diff between *original* and *revised* text.

    Args:
        original: The original text before revision.
        revised: The revised text after LLM changes.
        focus_areas: User-selected improvement focus areas
            (e.g. ``["dialogue", "description"]``). Used for change
            type classification.  When ``None`` or empty, all changes
            are classified as ``"word_choice"``.

    Returns:
        :class:`DiffResult` with grouped and classified changes.

    Edge cases:
        * Empty original or revised → result with ``has_changes=False``
        * Identical texts → result with ``has_changes=False``
        * Very radical rewrites → best-effort diff (may produce
          large replace operations)
    """
    focus = focus_areas or []

    if not original or not revised:
        return DiffResult(original=original, revised=revised)

    if original == revised:
        return DiffResult(original=original, revised=revised)

    # Step 1: Base diff via SequenceMatcher
    matcher = difflib.SequenceMatcher(None, original, revised)
    raw_ops = list(matcher.get_opcodes())

    # Step 2: Convert to DiffOp, filter "equal"
    diff_ops: list[DiffOp] = []
    for tag, i1, i2, j1, j2 in raw_ops:
        if tag == "equal":
            continue
        diff_ops.append(
            DiffOp(
                type=tag,  # pyright: ignore[argType]
                original_start=i1,
                original_end=i2,
                revised_start=j1,
                revised_end=j2,
                content_original=original[i1:i2],
                content_revised=revised[j1:j2],
            )
        )

    if not diff_ops:
        return DiffResult(original=original, revised=revised)

    # Step 3: Group by sentence boundary
    groups = group_by_sentence(diff_ops, original)

    # Step 4: Classify based on focus areas
    classified = classify_groups(groups, focus, original, revised)

    return DiffResult(
        original=original,
        revised=revised,
        changes=classified,
        total_changes=len(classified),
        has_changes=True,
    )


def has_meaningful_changes(result: DiffResult, min_changes: int = 1) -> bool:
    """Check whether *result* contains enough changes to display.

    Args:
        result: The diff result to evaluate.
        min_changes: Minimum number of change groups required.

    Returns:
        ``True`` when there are at least *min_changes* groups.
    """
    return result.has_changes and result.total_changes >= min_changes
