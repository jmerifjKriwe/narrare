"""SeriesConsistencyService graceful-degradation + ownership tests (Spec 4 Task 2).

Split from ``test_series_consistency_service.py`` for RULE-04 compliance (file
< 300 lines). Mirrors the analysis-lane precedent of splitting service tests by
concern (e.g. ``test_author_voice_drift_service.py`` +
``test_author_voice_drift_service_errors.py``).

This module covers:
- RULE-11 graceful degradation: no Canon OR no prose → empty result, no LLM.
- Ownership + novel-membership anti-enumeration (both → 403).

Fake-based per ADR-030 (see ``_series_consistency_test_helpers.py``).
"""

from __future__ import annotations

import uuid

import pytest

from narrare_core.series.schemas import Series
from narrare_core.shared.errors import ForbiddenError
from tests.factories import make_chapter, make_novel

from ._series_consistency_test_helpers import make_service, seed_owned_series_with_canon

# ---------------------------------------------------------------------------
# check_novel() — RULE-11 graceful degradation (no LLM call)
# ---------------------------------------------------------------------------


class TestCheckNovelGraceful:
    """No Canon OR no prose → empty result without an LLM call."""

    async def test_no_canon_entries_returns_empty_without_agent(self) -> None:
        user_id = uuid.uuid4()
        service, agent, _, series_repo, novel_repo, chapter_repo = make_service()
        # Seed series + novel + prose chapters but NO canon entries.
        series_id, novel_id = uuid.uuid4(), uuid.uuid4()
        series_repo.seed(Series(id=series_id, user_id=user_id, title="S", writing_language="en"))
        novel_repo.seed(make_novel(id=novel_id, user_id=user_id, series_id=series_id))
        chapter_repo.seed(make_chapter(novel_id=novel_id, content="Some prose."))

        result = await service.check_novel(series_id, novel_id, user_id)

        assert agent.run_count == 0
        assert result.conflicts == []
        assert result.canon_entry_count == 0

    async def test_no_chapter_prose_returns_empty_without_agent(self) -> None:
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
            chapter_prose=(),  # no chapters
        )

        result = await service.check_novel(series_id, novel_id, user_id)

        assert agent.run_count == 0
        assert result.conflicts == []
        assert result.chapter_count == 0

    async def test_only_blank_prose_returns_empty_without_agent(self) -> None:
        """Chapters with blank-only content count as no prose (RULE-11)."""
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, novel_id = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
            chapter_prose=("   ",),  # blank-only
        )

        result = await service.check_novel(series_id, novel_id, user_id)

        assert agent.run_count == 0
        assert result.conflicts == []


# ---------------------------------------------------------------------------
# check_novel() — ownership + membership anti-enumeration
# ---------------------------------------------------------------------------


class TestCheckNovelOwnership:
    """Anti-enumeration: missing/not-owned series + non-member novel → 403."""

    async def test_series_not_owned_raises_forbidden(self) -> None:
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, _ = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        with pytest.raises(ForbiddenError):
            await service.check_novel(series_id, uuid.uuid4(), uuid.uuid4())

        assert agent.run_count == 0

    async def test_series_missing_raises_forbidden(self) -> None:
        """A missing series surfaces as 403 (never 404 — anti-enumeration)."""
        user_id = uuid.uuid4()
        service, agent, *_ = make_service()

        with pytest.raises(ForbiddenError):
            await service.check_novel(uuid.uuid4(), uuid.uuid4(), user_id)

        assert agent.run_count == 0

    async def test_novel_not_in_series_raises_forbidden(self) -> None:
        """A novel whose series_id != series_id surfaces as 403 (anti-enumeration)."""
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, _ = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )
        # A novel in a DIFFERENT series.
        other_series = uuid.uuid4()
        other_novel = uuid.uuid4()
        novel_repo.seed(make_novel(id=other_novel, user_id=user_id, series_id=other_series))

        with pytest.raises(ForbiddenError):
            await service.check_novel(series_id, other_novel, user_id)

        assert agent.run_count == 0

    async def test_novel_missing_raises_forbidden(self) -> None:
        """A missing novel surfaces as 403 (never 404 — anti-enumeration)."""
        user_id = uuid.uuid4()
        service, agent, kb_repo, series_repo, novel_repo, chapter_repo = make_service()
        series_id, _ = seed_owned_series_with_canon(
            series_repo=series_repo,
            novel_repo=novel_repo,
            chapter_repo=chapter_repo,
            kb_repo=kb_repo,
            user_id=user_id,
        )

        with pytest.raises(ForbiddenError):
            await service.check_novel(series_id, uuid.uuid4(), user_id)

        assert agent.run_count == 0
