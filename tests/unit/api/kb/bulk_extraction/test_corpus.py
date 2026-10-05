"""Corpus pass scope module (pure) unit tests (F3 T1, spec §4 / D20a).

``corpus.py`` is pure by construction: chapter rows in → deterministic scope
decision + honest estimate out (no I/O, no DB). These tests pin the D20a
protocol constants, the longest-position-order-prefix selection under both
caps, the never-skipping prefix rule, the empty-prefix ``ValidationError``
guidance, and the 1:1 estimate mapping T2 mirrors in ``CorpusEstimateView``.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare.kb.bulk_extraction.contracts import (
    BulkChapterRef,
    CorpusChapterRow,
    CorpusChapterSource,
)
from narrare.kb.bulk_extraction.corpus import (
    CORPUS_PASS_MAX_CHAPTERS,
    CORPUS_PASS_MAX_WORDS,
    build_estimate,
    select_corpus_prefix,
)
from narrare_core.shared.errors import ValidationError


def _row(position: int, word_count: int, *, title: str = "Chapter") -> CorpusChapterRow:
    return CorpusChapterRow(
        chapter_id=uuid4(),
        title=title,
        position=position,
        word_count=word_count,
    )


def _rows(
    count: int, words_each: int, *, start: int = 1, title_prefix: str = "Chapter"
) -> list[CorpusChapterRow]:
    return [
        CorpusChapterRow(
            chapter_id=uuid4(),
            title=f"{title_prefix} {i}",
            position=i,
            word_count=words_each,
        )
        for i in range(start, start + count)
    ]


class TestConstants:
    def test_caps_pinned(self) -> None:
        assert CORPUS_PASS_MAX_CHAPTERS == 120
        assert CORPUS_PASS_MAX_WORDS == 200_000


class TestSelection:
    def test_small_novel_selects_everything(self) -> None:
        rows = _rows(3, 3_000)

        selection = select_corpus_prefix(rows)

        assert selection.selected == tuple(rows)
        assert selection.total_chapters == 3
        assert selection.total_word_count == 9_000
        assert selection.selected_word_count == 9_000
        assert selection.capped is False
        assert selection.cap_reason is None

    def test_chapter_cap_bites_first(self) -> None:
        rows = _rows(150, 1_000)

        selection = select_corpus_prefix(rows)

        assert len(selection.selected) == 120
        assert [ref.chapter_id for ref in selection.selected] == [
            row.chapter_id for row in rows[:120]
        ]
        assert selection.total_chapters == 150
        assert selection.total_word_count == 150_000
        assert selection.selected_word_count == 120_000
        assert selection.capped is True
        assert selection.cap_reason == "chapters"

    def test_word_cap_bites_first(self) -> None:
        rows = _rows(90, 2_400)  # 216k total — 83 chapters fit (199.2k), 84 do not

        selection = select_corpus_prefix(rows)

        assert len(selection.selected) == 83
        assert selection.selected_word_count == 199_200
        assert selection.total_chapters == 90
        assert selection.total_word_count == 216_000
        assert selection.capped is True
        assert selection.cap_reason == "words"

    def test_boundary_exact_fit_is_not_capped(self) -> None:
        rows = _rows(119, 1_600)  # 190,400
        rows.append(_row(120, 9_600, title="Chapter 120"))  # exactly 200,000 total

        selection = select_corpus_prefix(rows)

        assert len(selection.selected) == 120
        assert selection.selected_word_count == 200_000
        assert selection.capped is False
        assert selection.cap_reason is None

    def test_prefix_never_skips(self) -> None:
        rows = [
            *_rows(3, 50_000),  # 150k — fits
            _row(4, 60_000, title="Chapter 4"),  # would push to 210k → boundary
            _row(5, 1_000, title="Chapter 5"),  # small, but NOT reachable (strict prefix)
        ]

        selection = select_corpus_prefix(rows)

        assert [ref.position for ref in selection.selected] == [1, 2, 3]
        assert selection.capped is True
        assert selection.cap_reason == "words"
        assert selection.total_chapters == 5
        assert selection.total_word_count == 211_000

    def test_selection_is_deterministic(self) -> None:
        rows = _rows(150, 1_000)

        assert select_corpus_prefix(rows) == select_corpus_prefix(rows)

    def test_empty_input_returns_empty_selection(self) -> None:
        selection = select_corpus_prefix([])

        assert selection.selected == ()
        assert selection.total_chapters == 0
        assert selection.total_word_count == 0
        assert selection.selected_word_count == 0
        assert selection.capped is False
        assert selection.cap_reason is None

    def test_single_oversized_chapter_rejected(self) -> None:
        row = _row(1, 250_000, title="The Colossus")

        with pytest.raises(ValidationError) as excinfo:
            select_corpus_prefix([row])

        message = str(excinfo.value)
        assert "The Colossus" in message
        assert "250000" in message
        assert "200000" in message
        assert "1 chapters" in message  # honest total_chapters count
        assert "split" in message.lower()

    @pytest.mark.parametrize(
        "positions",
        [(2, 2), (2, 1)],
        ids=["duplicate-position", "descending-positions"],
    )
    def test_non_monotonic_positions_rejected(self, positions: tuple[int, int]) -> None:
        rows = [_row(positions[0], 100), _row(positions[1], 100)]

        with pytest.raises(ValidationError, match="position"):
            select_corpus_prefix(rows)

    def test_negative_word_count_rejected(self) -> None:
        rows = [_row(1, -5, title="Broken")]

        with pytest.raises(ValidationError, match="word count"):
            select_corpus_prefix(rows)


class TestEstimate:
    def test_estimate_fields(self) -> None:
        rows = _rows(150, 1_000)

        estimate = build_estimate(select_corpus_prefix(rows))

        assert estimate.total_chapters == 150
        assert estimate.total_word_count == 150_000
        assert estimate.selected_chapter_ids == tuple(row.chapter_id for row in rows[:120])
        assert estimate.chapter_count == 120
        assert estimate.word_count == 120_000
        assert estimate.ai_calls == 120
        assert estimate.capped is True
        assert estimate.cap_reason == "chapters"

    def test_estimate_uncapped_mirrors_totals(self) -> None:
        rows = _rows(3, 3_000)

        estimate = build_estimate(select_corpus_prefix(rows))

        assert estimate.chapter_count == estimate.total_chapters == 3
        assert estimate.word_count == estimate.total_word_count == 9_000
        assert estimate.ai_calls == 3
        assert estimate.capped is False
        assert estimate.cap_reason is None


class TestContracts:
    def test_row_is_a_bulk_chapter_ref(self) -> None:
        row = _row(1, 1_000)

        assert isinstance(row, BulkChapterRef)

    def test_source_protocol_shape(self) -> None:
        class FakeSource:
            async def load_all(self, novel_id: UUID) -> list[CorpusChapterRow]:
                return []

        assert isinstance(FakeSource(), CorpusChapterSource)
