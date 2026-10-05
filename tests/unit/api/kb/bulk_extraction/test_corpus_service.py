"""Corpus estimate/start service + job-kind/dedup unit tests (F3 T2, spec §4).

Covers the plan T2 list: the ownership gate BEFORE enumeration (IDOR
ordering), the honest-0 estimate for a zero-chapter novel (estimate-only —
START rejects emptiness, rider b), capped/uncapped estimate view fields,
the START-time re-validation (estimate drift → job over the START-time
prefix, spec R3/R4 — never a silent superset, rider d), the reused
single-active-job 409, ``kind="corpus"`` on create + dispatch, the
registry-side dedup block defaults/flips (explicit ≡ ``None``; corpus
defaults to ``analyzed: false``; ``mark_dedup`` / ``mark_dedup_unavailable``
flip it), and the wire self-defending invariants of the new schemas.

Fakes implement the T1 Protocols (no mocks — RULE-TEST-01); the corpus
source fake replays scripted row lists so the estimate-vs-start drift is
observable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from narrare.kb.bulk_extraction import registry
from narrare.kb.bulk_extraction.contracts import (
    BulkExtractionDispatcher,
    BulkExtractionJobStore,
    CorpusChapterRow,
    CorpusChapterSource,
)
from narrare.kb.bulk_extraction.schemas_corpus import BulkDedupInfo, CorpusEstimateView
from narrare.kb.bulk_extraction.service import BulkExtractionService
from narrare.novels.models import Novel
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.unit.api.kb._bulk_extraction_fakes import (
    NOVEL_ID,
    OWNER,
)
from tests.unit.api.kb._bulk_extraction_fakes import (
    FakeCorpusSource as _FakeCorpusSource,
)
from tests.unit.api.kb._bulk_extraction_fakes import (
    FakeDispatcher as _FakeDispatcher,
)
from tests.unit.api.kb._bulk_extraction_fakes import (
    FakeReader as _FakeReader,
)
from tests.unit.api.kb._bulk_extraction_fakes import (
    FakeStore as _FakeStore,
)
from tests.unit.api.kb._bulk_extraction_fakes import (
    make_ref as _ref,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


def _row(position: int, words: int = 1_000) -> CorpusChapterRow:
    return CorpusChapterRow(
        chapter_id=uuid4(),
        title=f"Chapter {position}",
        position=position,
        word_count=words,
    )


def _rows(count: int, words_each: int = 1_000) -> list[CorpusChapterRow]:
    return [_row(index + 1, words_each) for index in range(count)]


def _owned_novel_repo() -> FakeNovelRepository:
    """Gate repo with the owned novel seeded (gate passes)."""
    repo = FakeNovelRepository()
    repo.seed(Novel(id=NOVEL_ID, user_id=OWNER, title="Owned"))
    return repo


class _Harness:
    """The service plus its fakes, wired exactly as production would."""

    def __init__(
        self,
        *,
        store: _FakeStore | None = None,
        source: _FakeCorpusSource | None = None,
        novel_repo: FakeNovelRepository | None = None,
    ) -> None:
        self.store = store or _FakeStore()
        self.source = source or _FakeCorpusSource([_rows(3)])
        self.dispatcher = _FakeDispatcher()
        self.novel_repo = novel_repo or _owned_novel_repo()
        self.service = BulkExtractionService(
            store=self.store,
            reader=_FakeReader(),
            corpus_source=self.source,
            dispatcher=self.dispatcher,
            novel_repo=self.novel_repo,
        )


class TestProtocolConformance:
    def test_fakes_satisfy_the_protocols(self) -> None:
        harness = _Harness()

        assert isinstance(harness.source, CorpusChapterSource)
        assert isinstance(harness.store, BulkExtractionJobStore)
        assert isinstance(harness.dispatcher, BulkExtractionDispatcher)


class TestEstimate:
    async def test_gates_ownership_before_enumeration(self) -> None:
        harness = _Harness(novel_repo=FakeNovelRepository())  # nothing seeded → 404

        with pytest.raises(NotFoundError, match="Novel"):
            await harness.service.corpus_estimate(NOVEL_ID, OWNER)

        assert len(harness.novel_repo.calls) == 1  # the gate ran (and only it)
        assert harness.source.calls == []  # gate BEFORE enumeration (IDOR ordering)

    async def test_zero_chapter_novel_is_an_honest_zero(self) -> None:
        """Rider b: empty selection is honest-0 for the ESTIMATE endpoint."""
        harness = _Harness(source=_FakeCorpusSource([[]]))

        view = await harness.service.corpus_estimate(NOVEL_ID, OWNER)

        assert isinstance(view, CorpusEstimateView)
        assert view.total_chapters == 0
        assert view.total_word_count == 0
        assert view.selected_chapter_ids == []
        assert view.chapter_count == 0
        assert view.word_count == 0
        assert view.ai_calls == 0
        assert view.capped is False
        assert view.cap_reason is None

    async def test_small_novel_estimate_mirrors_the_selection(self) -> None:
        rows = _rows(3)
        harness = _Harness(source=_FakeCorpusSource([rows]))

        view = await harness.service.corpus_estimate(NOVEL_ID, OWNER)

        assert view.total_chapters == 3
        assert view.total_word_count == 3_000
        assert view.selected_chapter_ids == [row.chapter_id for row in rows]
        assert view.chapter_count == 3
        assert view.word_count == 3_000
        assert view.ai_calls == 3  # D14a: one call per chapter
        assert view.capped is False
        assert view.cap_reason is None

    async def test_capped_corpus_estimate_is_honest(self) -> None:
        rows = _rows(150)  # 150k words — the chapter cap bites at 120
        harness = _Harness(source=_FakeCorpusSource([rows]))

        view = await harness.service.corpus_estimate(NOVEL_ID, OWNER)

        assert view.total_chapters == 150
        assert view.total_word_count == 150_000
        assert view.selected_chapter_ids == [row.chapter_id for row in rows[:120]]
        assert view.chapter_count == 120
        assert view.word_count == 120_000
        assert view.ai_calls == 120
        assert view.capped is True
        assert view.cap_reason == "chapters"


class TestStart:
    async def test_gates_ownership_before_enumeration(self) -> None:
        harness = _Harness(novel_repo=FakeNovelRepository())  # nothing seeded → 404

        with pytest.raises(NotFoundError, match="Novel"):
            await harness.service.start_corpus(NOVEL_ID, OWNER)

        assert harness.source.calls == []
        assert harness.store.created_with is None
        assert harness.dispatcher.dispatched == []

    async def test_revalidates_at_start_time(self) -> None:
        """Rider d / spec R3: the job runs over the START-time prefix.

        The estimate showed 3 chapters; two more arrived before the start —
        the source is re-loaded and the job covers the NEW prefix, never a
        silent superset of what the estimate showed.
        """
        before = _rows(3)
        after = _rows(5)
        harness = _Harness(source=_FakeCorpusSource([before, after]))

        estimate = await harness.service.corpus_estimate(NOVEL_ID, OWNER)
        assert estimate.chapter_count == 3

        view = await harness.service.start_corpus(NOVEL_ID, OWNER)

        assert view.job_id == "job-1"
        assert view.totals.total == 5
        assert harness.source.calls == [NOVEL_ID, NOVEL_ID]  # re-loaded at start
        assert harness.store.created_with is not None
        created_novel, created_owner, created_refs = harness.store.created_with
        assert (created_novel, created_owner) == (NOVEL_ID, OWNER)
        assert harness.store.created_kind == "corpus"  # the post-pass trigger kind
        assert [ref.chapter_id for ref in created_refs] == [row.chapter_id for row in after]
        assert harness.dispatcher.dispatched == [("job-1", NOVEL_ID, OWNER)]

    async def test_reuses_the_single_active_job_rule(self) -> None:
        harness = _Harness(store=_FakeStore(active=True))

        with pytest.raises(ConflictError, match="already active"):
            await harness.service.start_corpus(NOVEL_ID, OWNER)

        assert harness.store.created_with is None  # 409 before any record exists
        assert harness.dispatcher.dispatched == []

    async def test_zero_chapter_novel_is_rejected(self) -> None:
        """Rider b: START (unlike the estimate) rejects an empty selection."""
        harness = _Harness(source=_FakeCorpusSource([[]]))

        with pytest.raises(ValidationError, match="0 chapters"):
            await harness.service.start_corpus(NOVEL_ID, OWNER)

        assert harness.store.created_with is None
        assert harness.dispatcher.dispatched == []

    async def test_oversized_first_chapter_is_rejected(self) -> None:
        """Rider c: the selection's ValidationError propagates (→ 422)."""
        harness = _Harness(source=_FakeCorpusSource([[_row(1, 250_000)]]))

        with pytest.raises(ValidationError, match="Split"):
            await harness.service.start_corpus(NOVEL_ID, OWNER)

        assert harness.store.created_with is None
        assert harness.dispatcher.dispatched == []


class TestRegistryJobKindAndDedup:
    """Registry-level kind/dedup state (T3's runner consumes these seams)."""

    @pytest.fixture(autouse=True)
    def _clear_jobs(self) -> Iterator[None]:
        registry._JOBS.clear()
        yield
        registry._JOBS.clear()

    def test_explicit_job_has_no_dedup_block(self) -> None:
        job_id = registry.create(NOVEL_ID, OWNER, [_ref(1)]).job_id

        assert registry.kind_of(job_id) == "explicit"
        assert registry.status(job_id, OWNER).dedup is None
        assert registry.results(job_id, OWNER).dedup is None

    def test_corpus_job_defaults_to_the_unanalyzed_dedup_block(self) -> None:
        job_id = registry.create(NOVEL_ID, OWNER, [_ref(1)], kind="corpus").job_id

        assert registry.kind_of(job_id) == "corpus"
        expected = BulkDedupInfo(analyzed=False, suggestion_count=None)
        assert registry.status(job_id, OWNER).dedup == expected
        assert registry.results(job_id, OWNER).dedup == expected

    def test_mark_dedup_flips_both_fields(self) -> None:
        job_id = registry.create(NOVEL_ID, OWNER, [_ref(1)], kind="corpus").job_id

        registry.mark_dedup(job_id, 7)

        assert registry.status(job_id, OWNER).dedup == BulkDedupInfo(
            analyzed=True, suggestion_count=7
        )

    def test_mark_dedup_unavailable_resets_the_block(self) -> None:
        job_id = registry.create(NOVEL_ID, OWNER, [_ref(1)], kind="corpus").job_id

        registry.mark_dedup(job_id, 7)
        registry.mark_dedup_unavailable(job_id)

        assert registry.status(job_id, OWNER).dedup == BulkDedupInfo(
            analyzed=False, suggestion_count=None
        )

    def test_kind_of_unknown_job_degrades_to_explicit(self) -> None:
        """A swept/unknown id must never arm the post-pass trigger (T3)."""

        assert registry.kind_of("no-such-job") == "explicit"


class TestCorpusSchemas:
    """Wire self-defending invariants of the F3 schema additions."""

    def test_dedup_count_requires_analyzed(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkDedupInfo(analyzed=True, suggestion_count=None)

    def test_dedup_count_forbidden_when_not_analyzed(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkDedupInfo(analyzed=False, suggestion_count=3)

    def test_dedup_zero_suggestions_is_valid(self) -> None:
        info = BulkDedupInfo(analyzed=True, suggestion_count=0)

        assert info.analyzed is True
        assert info.suggestion_count == 0

    def test_dedup_rejects_unknown_fields(self) -> None:
        with pytest.raises(PydanticValidationError):
            BulkDedupInfo.model_validate(
                {"analyzed": False, "suggestion_count": None, "extra": "x"}
            )

    def test_estimate_view_rejects_ai_call_mismatch(self) -> None:
        with pytest.raises(PydanticValidationError):
            CorpusEstimateView(
                total_chapters=3,
                total_word_count=3_000,
                selected_chapter_ids=[uuid4()],
                chapter_count=3,
                word_count=3_000,
                ai_calls=2,  # ≠ chapter_count — D14a forbids this
                capped=False,
                cap_reason=None,
            )
