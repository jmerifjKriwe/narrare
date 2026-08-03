"""Unit tests for BandSummaryService (Spec 2 — Series Generation Context, Task 3).

Fake-based per ADR-030: domain dependencies (repositories, composer, registry,
agent) are real Fake classes from ``_band_summary_test_helpers.py`` — no
``MagicMock``/``patch`` for domain behaviour. The agent is injectable via
``agent_factory`` so tests supply a fake whose ``.run()`` returns a controlled
``BandSummaryOutput``.

Chapter summaries live on ``Chapter.summary`` (``chapters/models.py``); the
service fetches them via ``list_by_novel`` and aggregates the non-empty ones.
"""

from __future__ import annotations

import uuid

import pytest

from narrare.series.band_summary_models import BandSummary
from narrare_core.shared.errors import NotFoundError, ValidationError, WritingError
from tests.factories import make_chapter, make_novel
from tests.fakes.fake_band_summary_repo import FakeBandSummaryRepository
from tests.fakes.fake_chapter_repo import FakeChapterRepository
from tests.fakes.fake_novel_repo import FakeNovelRepository

from ._band_summary_test_helpers import (
    FakeBandSummaryAgent,
    make_band_summary_service,
)

# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


class TestGenerate:
    """BandSummaryService.generate() — happy path + error paths."""

    async def test_generate_with_chapter_summaries_upserts_and_returns(self) -> None:
        """Happy path: novel + summaries → agent run → upsert full+short."""
        novel_id = uuid.uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id, title="The Forbidden Vale", genre="Fantasy"))
        chapter_repo = FakeChapterRepository()
        chapter_repo.seed(
            make_chapter(novel_id=novel_id, position=1, summary="Hero arrives."),
            make_chapter(novel_id=novel_id, position=2, summary="Secret revealed."),
        )

        service, agent, repo = make_band_summary_service(
            novel_repo=novel_repo, chapter_repo=chapter_repo
        )

        result = await service.generate(novel_id)

        # Agent ran once with both summaries in deps (ordered, non-empty).
        assert agent.run_count == 1
        assert agent.last_deps.novel_title == "The Forbidden Vale"
        assert agent.last_deps.genre == "Fantasy"
        assert agent.last_deps.chapter_summaries == ["Hero arrives.", "Secret revealed."]
        # The joined summaries flow as runtime content in the run prompt.
        assert "Hero arrives." in agent.last_prompt
        assert "Secret revealed." in agent.last_prompt

        # Upserted with the agent output.
        repo.assert_called_once("upsert")
        assert result.full_summary == "The hero prevails and the realm is restored."
        assert result.short_summary == "A hero restores a fractured realm."
        assert result.novel_id == novel_id

    async def test_generate_skips_empty_chapter_summaries(self) -> None:
        """Chapters whose ``summary`` is empty/blank are excluded from aggregation."""
        novel_id = uuid.uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id))
        chapter_repo = FakeChapterRepository()
        chapter_repo.seed(
            make_chapter(novel_id=novel_id, position=1, summary="Real summary."),
            make_chapter(novel_id=novel_id, position=2, summary=""),  # empty → skipped
            make_chapter(novel_id=novel_id, position=3, summary="   "),  # blank → skipped
        )

        service, agent, _ = make_band_summary_service(
            novel_repo=novel_repo, chapter_repo=chapter_repo
        )

        await service.generate(novel_id)

        assert agent.last_deps.chapter_summaries == ["Real summary."]

    async def test_generate_with_unknown_novel_raises_not_found(self) -> None:
        """Missing novel surfaces as NotFoundError (no silent skip)."""
        service, _, repo = make_band_summary_service()

        with pytest.raises(NotFoundError, match="Novel"):
            await service.generate(novel_id=uuid.uuid4())

        repo.assert_not_called("upsert")

    async def test_generate_with_no_chapter_summaries_raises_validation(self) -> None:
        """RULE-11: a novel with no summaries cannot be aggregated.

        The agent validator requires non-empty output, so generating with no
        input would hallucinate. We fail fast with an explicit, catchable
        ValidationError so callers (auto-trigger, lazy tier) can degrade.
        """
        novel_id = uuid.uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id))
        chapter_repo = FakeChapterRepository()
        chapter_repo.seed(make_chapter(novel_id=novel_id, summary=""))  # only blank

        service, agent, repo = make_band_summary_service(
            novel_repo=novel_repo, chapter_repo=chapter_repo
        )

        with pytest.raises(ValidationError, match="chapter summar"):
            await service.generate(novel_id)

        assert agent.run_count == 0
        repo.assert_not_called("upsert")

    async def test_generate_when_agent_fails_wraps_in_writing_error(self) -> None:
        """Agent failure is wrapped in WritingError (RULE-11: no bare raise)."""
        novel_id = uuid.uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id))
        chapter_repo = FakeChapterRepository()
        chapter_repo.seed(make_chapter(novel_id=novel_id, summary="Some summary."))

        failing_agent = FakeBandSummaryAgent(raises=RuntimeError("LLM down"))
        service, _, repo = make_band_summary_service(
            novel_repo=novel_repo, chapter_repo=chapter_repo, agent=failing_agent
        )

        with pytest.raises(WritingError, match="Band summary generation failed"):
            await service.generate(novel_id)

        repo.assert_not_called("upsert")

    async def test_generate_re_raises_not_found_from_agent(self) -> None:
        """NotFoundError raised inside the flow is re-raised, not wrapped."""
        novel_id = uuid.uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id))
        chapter_repo = FakeChapterRepository()
        chapter_repo.seed(make_chapter(novel_id=novel_id, summary="Summary."))

        failing_agent = FakeBandSummaryAgent(
            raises=NotFoundError("Novel", identifier=str(novel_id))
        )
        service, _, _ = make_band_summary_service(
            novel_repo=novel_repo, chapter_repo=chapter_repo, agent=failing_agent
        )

        with pytest.raises(NotFoundError):
            await service.generate(novel_id)


# ---------------------------------------------------------------------------
# get_or_generate()
# ---------------------------------------------------------------------------


class TestGetOrGenerate:
    """BandSummaryService.get_or_generate() — lazy semantics."""

    async def test_returns_existing_when_full_summary_present(self) -> None:
        """Existing generated summary is returned without re-generating."""
        novel_id = uuid.uuid4()
        existing = BandSummary(
            novel_id=novel_id, full_summary="old full", short_summary="old short"
        )
        repo = FakeBandSummaryRepository()
        repo.seed(existing)

        service, agent, _ = make_band_summary_service(repo=repo)

        result = await service.get_or_generate(novel_id)

        assert result is existing
        assert agent.run_count == 0
        repo.assert_not_called("upsert")

    async def test_returns_existing_when_only_override_present(self) -> None:
        """An override (even without generated text) satisfies the cache."""
        novel_id = uuid.uuid4()
        existing = BandSummary(novel_id=novel_id, override="user override text")
        repo = FakeBandSummaryRepository()
        repo.seed(existing)

        service, agent, _ = make_band_summary_service(repo=repo)

        result = await service.get_or_generate(novel_id)

        assert result is existing
        assert agent.run_count == 0

    async def test_generates_when_no_existing_row(self) -> None:
        """No row → triggers generation (lazy)."""
        novel_id = uuid.uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id))
        chapter_repo = FakeChapterRepository()
        chapter_repo.seed(make_chapter(novel_id=novel_id, summary="Summary."))

        service, agent, repo = make_band_summary_service(
            novel_repo=novel_repo, chapter_repo=chapter_repo
        )

        result = await service.get_or_generate(novel_id)

        assert agent.run_count == 1
        repo.assert_called_once("upsert")
        assert result.full_summary == "The hero prevails and the realm is restored."

    async def test_regenerates_when_row_exists_but_empty(self) -> None:
        """A row with neither override nor full_summary is treated as missing."""
        novel_id = uuid.uuid4()
        novel_repo = FakeNovelRepository()
        novel_repo.seed(make_novel(id=novel_id))
        chapter_repo = FakeChapterRepository()
        chapter_repo.seed(make_chapter(novel_id=novel_id, summary="Summary."))

        repo = FakeBandSummaryRepository()
        repo.seed(BandSummary(novel_id=novel_id))  # empty row

        service, agent, _ = make_band_summary_service(
            novel_repo=novel_repo, chapter_repo=chapter_repo, repo=repo
        )

        await service.get_or_generate(novel_id)

        assert agent.run_count == 1


# ---------------------------------------------------------------------------
# update_override()
# ---------------------------------------------------------------------------


class TestUpdateOverride:
    """BandSummaryService.update_override() — set / clear routing."""

    async def test_set_override_with_value_calls_set_override(self) -> None:
        novel_id = uuid.uuid4()
        service, _, repo = make_band_summary_service()

        result = await service.update_override(novel_id, "custom override")

        repo.assert_called_once("set_override")
        repo.assert_called("set_override", novel_id=novel_id, override="custom override")
        assert result.override == "custom override"

    async def test_update_override_with_none_calls_clear(self) -> None:
        novel_id = uuid.uuid4()
        service, _, repo = make_band_summary_service()

        result = await service.update_override(novel_id, None)

        repo.assert_called_once("clear_override")
        repo.assert_not_called("set_override")
        assert result.override is None

    async def test_update_override_with_empty_string_calls_clear(self) -> None:
        """An empty/whitespace override is treated as 'clear' (no empty override)."""
        novel_id = uuid.uuid4()
        service, _, repo = make_band_summary_service()

        await service.update_override(novel_id, "   ")

        repo.assert_called_once("clear_override")
        repo.assert_not_called("set_override")
