"""Corpus pass scope — deterministic prefix selection + honest estimate (F3 T1).

Pure module (spec §4 / D20a): :class:`CorpusChapterRow` sequence in →
:class:`CorpusSelection` / :class:`CorpusEstimateData` out. No I/O, no DB, no
pydantic — T2 mirrors the estimate dataclass 1:1 in ``CorpusEstimateView``.

Selection rule: the **longest prefix** of the novel's position order that
satisfies ``len(prefix) <= CORPUS_PASS_MAX_CHAPTERS`` and
``sum(word_count) <= CORPUS_PASS_MAX_WORDS``. Deterministic — the same row
list always yields the same selection. Never silent: truncation is reported
via ``capped``/``cap_reason``; an empty prefix (the first chapter alone
exceeds the word cap) raises :class:`ValidationError` with split-first
guidance instead of quietly running nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from narrare_core.shared.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from narrare.kb.bulk_extraction.contracts import BulkChapterRef, CorpusChapterRow

#: Product cap — protocol constant (D20a), no settings surface (RULE-18b).
#: Pinned by test; revisiting it is a one-line change + test update.
CORPUS_PASS_MAX_CHAPTERS: Final[int] = 120

#: Product cap — protocol constant (D20a), no settings surface (RULE-18b).
CORPUS_PASS_MAX_WORDS: Final[int] = 200_000

#: Which cap truncated the selection (``None`` when nothing was truncated).
CapReason = Literal["chapters", "words"]


@dataclass(frozen=True, slots=True)
class CorpusSelection:
    """Outcome of the prefix selection over one novel's chapter rows."""

    #: The selected prefix, in position order (a strict prefix — never skips).
    selected: tuple[BulkChapterRef, ...]
    #: Honest totals over ALL enumerated rows (never just the selection).
    total_chapters: int
    total_word_count: int
    #: Word sum of ``selected`` (what the run will actually cost).
    selected_word_count: int
    capped: bool
    cap_reason: CapReason | None


@dataclass(frozen=True, slots=True)
class CorpusEstimateData:
    """Pre-run estimate (spec §4.3) — mirrored 1:1 by T2's ``CorpusEstimateView``.

    ``ai_calls == chapter_count`` (D14a: one extraction call per chapter —
    cost transparency is a count, never a vague "may take a while").
    """

    total_chapters: int
    total_word_count: int
    selected_chapter_ids: tuple[UUID, ...]
    chapter_count: int
    word_count: int
    ai_calls: int
    capped: bool
    cap_reason: CapReason | None


def _validate_rows(chapters: Sequence[CorpusChapterRow]) -> None:
    """Guard the caller contract: rows in position order, sane word counts.

    The service passes repository rows already ordered by ``position``; a
    violation here is a wiring bug, surfaced as ``ValidationError`` (422 at
    the boundary) rather than a silent mis-selection.
    """
    previous: int | None = None
    for row in chapters:
        if previous is not None and row.position <= previous:
            raise ValidationError(
                f"Corpus chapters must arrive in strictly increasing position "
                f"order: '{row.title}' at position {row.position} follows "
                f"position {previous}."
            )
        if row.word_count < 0:
            raise ValidationError(
                f"Corpus chapter '{row.title}' has a negative word count "
                f"({row.word_count}); word counts must be >= 0."
            )
        previous = row.position


def select_corpus_prefix(chapters: Sequence[CorpusChapterRow]) -> CorpusSelection:
    """Select the longest position-order prefix fitting both D20a caps.

    Rows must already be in position order (asserted). An empty input (a
    novel without chapters) yields an honest empty selection; a non-empty
    input whose first chapter alone exceeds the word cap raises
    :class:`ValidationError` carrying the honest counts and split-first
    guidance.
    """
    _validate_rows(chapters)

    total_chapters = len(chapters)
    total_word_count = sum(row.word_count for row in chapters)

    selected: list[CorpusChapterRow] = []
    selected_word_count = 0
    for row in chapters:
        if len(selected) >= CORPUS_PASS_MAX_CHAPTERS:
            break
        if selected_word_count + row.word_count > CORPUS_PASS_MAX_WORDS:
            break
        selected.append(row)
        selected_word_count += row.word_count

    if total_chapters > 0 and not selected:
        first = chapters[0]
        raise ValidationError(
            f"Corpus pass cannot start: the first of {total_chapters} chapters, "
            f"'{first.title}', alone has {first.word_count} words — over the "
            f"{CORPUS_PASS_MAX_WORDS} word per-run cap. Split the chapter "
            f"first, then run the pass again."
        )

    capped = len(selected) < total_chapters
    cap_reason: CapReason | None = None
    if capped:
        # The loop only stops short of the chapter cap when the word cap
        # bites first; otherwise the chapter cap is the binding constraint.
        cap_reason = "chapters" if len(selected) == CORPUS_PASS_MAX_CHAPTERS else "words"

    return CorpusSelection(
        selected=tuple(selected),
        total_chapters=total_chapters,
        total_word_count=total_word_count,
        selected_word_count=selected_word_count,
        capped=capped,
        cap_reason=cap_reason,
    )


def build_estimate(selection: CorpusSelection) -> CorpusEstimateData:
    """Map a selection to the estimate surface (never understates: D20a)."""
    return CorpusEstimateData(
        total_chapters=selection.total_chapters,
        total_word_count=selection.total_word_count,
        selected_chapter_ids=tuple(ref.chapter_id for ref in selection.selected),
        chapter_count=len(selection.selected),
        word_count=selection.selected_word_count,
        ai_calls=len(selection.selected),
        capped=selection.capped,
        cap_reason=selection.cap_reason,
    )


__all__ = [
    "CORPUS_PASS_MAX_CHAPTERS",
    "CORPUS_PASS_MAX_WORDS",
    "CapReason",
    "CorpusEstimateData",
    "CorpusSelection",
    "build_estimate",
    "select_corpus_prefix",
]
