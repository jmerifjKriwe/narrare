# packages/core/narrare_core/importing/operations.py
"""Split/merge operation-set semantics for import F1 — pure, deterministic.

Vocabulary v2 (ADR-091 Amendment 2):

- ``splits``/``merges`` address ORIGINAL detected-chapter indices — the
  preview ``items[].index`` space, re-derived identically at commit.
- ``excluded_indices``/``title_overrides`` (applied by the API service
  AFTER :func:`apply_operations`) address FINAL indices — the materialized
  list. Identity property: an empty op set maps final space onto original
  space, so v1 payloads keep their exact meaning.

Order freedom: every op is keyed on original indices and op sets are
pairwise disjoint (split ∩ merge = ∅; merges non-overlapping), so the
declared order of ops never affects the materialized result. The same
freedom extends one level down: a merge's ``indices`` and a split's
``at`` may be declared in any order — both validation and materialization
consume the sorted (canonical) form.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from narrare_core.importing.candidates import find_split_candidates
from narrare_core.importing.models import DetectedChapter
from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class SplitOperation:
    """Split one original chapter at the given candidate ordinals."""

    index: int
    at: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MergeOperation:
    """Merge a contiguous ascending run of original chapters (len >= 2).

    ``indices`` may be declared in any order; the canonical (sorted) run
    is what validation and materialization consume.
    """

    indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ImportOperationSet:
    splits: tuple[SplitOperation, ...] = ()
    merges: tuple[MergeOperation, ...] = ()


def build_operation_set(
    splits: Sequence[tuple[int, Sequence[int]]] = (),
    merges: Sequence[Sequence[int]] = (),
) -> ImportOperationSet:
    """Construct from primitives (the API layer's translation seam)."""
    return ImportOperationSet(
        splits=tuple(SplitOperation(index=index, at=tuple(at)) for index, at in splits),
        merges=tuple(MergeOperation(indices=tuple(indices)) for indices in merges),
    )


def validate_operations(chapters: Sequence[DetectedChapter], ops: ImportOperationSet) -> None:
    """Structural validation against the freshly (re-)parsed chapter list.

    Every rejection names the offending op (per-op drift detection): a
    stale preview surfaces as a targeted 422, never a silently wrong
    import (ADR-091 Amendment 2, spec §4.3).
    """
    chapter_count = len(chapters)
    split_indexes: set[int] = set()

    for op in ops.splits:
        _require_original_index(op.index, chapter_count, f"Split for chapter {op.index}")
        if op.index in split_indexes:
            raise ValidationError(f"Duplicate split operation for chapter {op.index}.")
        split_indexes.add(op.index)
        if not op.at:
            raise ValidationError(f"Split for chapter {op.index} selects no split points.")
        if len(set(op.at)) != len(op.at):
            raise ValidationError(f"Split for chapter {op.index} repeats a split point.")
        candidates = find_split_candidates(chapters[op.index].content)
        if not candidates:
            raise ValidationError(
                f"Split for chapter {op.index} selects split points, but the "
                f"chapter has no split candidates."
            )
        if min(op.at) < 0 or max(op.at) >= len(candidates):
            offender = min(op.at) if min(op.at) < 0 else max(op.at)
            raise ValidationError(
                f"Split point {offender} for chapter {op.index} is out of range "
                f"(0..{len(candidates) - 1})."
            )

    merged_indexes: set[int] = set()
    for op in ops.merges:
        indices = tuple(sorted(op.indices))
        if len(indices) < 2:
            raise ValidationError(f"Merge {list(op.indices)} must combine at least two chapters.")
        for position, index in enumerate(indices):
            _require_original_index(index, chapter_count, f"Merge {list(op.indices)}")
            if position and index != indices[position - 1] + 1:
                raise ValidationError(
                    f"Merge {list(op.indices)} is not contiguous at chapter {index}."
                )
            if index in merged_indexes:
                raise ValidationError(f"Chapter {index} appears in more than one merge.")
            if index in split_indexes:
                raise ValidationError(f"Chapter {index} cannot be both split and merged.")
            merged_indexes.add(index)


def apply_operations(
    chapters: Sequence[DetectedChapter], ops: ImportOperationSet
) -> list[DetectedChapter]:
    """Validate the op set, then materialize the final chapter list.

    Deterministic: identical chapters + identical op set ⇒ identical
    output. Application order is original chapter order (ops are folds,
    not rewrites).
    """
    validate_operations(chapters, ops)

    split_at = {op.index: tuple(sorted(op.at)) for op in ops.splits}
    merge_root: dict[int, int] = {}
    merge_members: dict[int, tuple[int, ...]] = {}
    for op in ops.merges:
        members = tuple(sorted(op.indices))
        merge_members[members[0]] = members
        for index in members:
            merge_root[index] = members[0]

    result: list[DetectedChapter] = []
    for index, chapter in enumerate(chapters):
        root = merge_root.get(index)
        if root is not None:
            if index == root:
                result.append(_merge_chapters(chapters, merge_members[root]))
            continue
        cuts = split_at.get(index)
        if cuts is not None:
            result.extend(_split_chapter(index, chapter, cuts))
            continue
        result.append(chapter)
    return result


def _require_original_index(index: int, chapter_count: int, context: str) -> None:
    if not 0 <= index < chapter_count:
        raise ValidationError(f"{context}: index {index} is out of range (0..{chapter_count - 1}).")


def _split_chapter(
    index: int, chapter: DetectedChapter, cuts: Sequence[int]
) -> list[DetectedChapter]:
    """Materialize split parts (v1 heading-split semantics at level 3+).

    Part 0 keeps the chapter title and the content before the first cut;
    part j >= 1 starts at its heading line — the heading becomes the part
    title and is NOT stored in the content (v1 rule). Unselected candidate
    headings between cuts stay inside the part content. Empty parts are
    dropped (v1 rules); if NO part survives, the op would delete the
    chapter — a loud ValidationError instead.
    """
    candidates = find_split_candidates(chapter.content)
    by_ordinal = {candidate.ordinal: candidate for candidate in candidates}
    selected = [by_ordinal[ordinal] for ordinal in cuts]
    bounds = [0] + [candidate.start for candidate in selected] + [len(chapter.content)]
    titles = [chapter.title] + [candidate.heading for candidate in selected]

    parts: list[DetectedChapter] = []
    for position in range(len(selected) + 1):
        segment = chapter.content[bounds[position] : bounds[position + 1]]
        if position > 0:
            # The heading line itself is not stored in the part content.
            newline = segment.find("\n")
            segment = segment[newline + 1 :] if newline != -1 else ""
        body = segment.strip()
        if not body:
            continue
        parts.append(
            DetectedChapter(
                title=titles[position],
                content=body,
                word_count=len(body.split()),
                status=chapter.status,
                source_file=chapter.source_file,
            )
        )
    if not parts:
        raise ValidationError(
            f"Split for chapter {index} would remove it entirely (no part has content)."
        )
    return parts


def _merge_chapters(
    chapters: Sequence[DetectedChapter], indices: tuple[int, ...]
) -> DetectedChapter:
    """Materialize one merged chapter (D5a).

    Title/status/source come from the FIRST constituent (documented
    coercion — other constituents' statuses are discarded). Contents join
    with one blank line; the word count is recomputed from the joined
    content.
    """
    members = [chapters[index] for index in indices]
    first = members[0]
    content = "\n\n".join(member.content for member in members)
    return DetectedChapter(
        title=first.title,
        content=content,
        word_count=len(content.split()),
        status=first.status,
        source_file=first.source_file,
    )
