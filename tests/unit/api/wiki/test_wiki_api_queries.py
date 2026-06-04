"""Unit tests for APIWikiService — summary queries and wiki index.

Tests ``get_summaries`` and ``get_wiki_index`` with proper Fakes (RULE-TEST-01).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .conftest import _NOVEL_ID, _USER_ID, _make_wiki_summary_row

if TYPE_CHECKING:
    from narrare.wiki.schemas import WikiIndexResponse, WikiSummaryListResponse
    from narrare.wiki.service import APIWikiService
    from tests.fakes import FakeWikiRepository

# ---------------------------------------------------------------------------
# Tests: get_summaries
# ---------------------------------------------------------------------------


class TestGetSummaries:
    """APIWikiService.get_summaries tests."""

    async def test_returns_all_summaries(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """Returns all summaries for the novel."""
        fake_wiki_repo.configure(
            "get_summaries",
            [
                _make_wiki_summary_row(status="fresh"),
                _make_wiki_summary_row(status="stale"),
            ],
        )

        result: WikiSummaryListResponse = await service.get_summaries(
            _NOVEL_ID, _USER_ID, entity_ids=None
        )

        assert result.total == 2
        assert len(result.items) == 2

    async def test_filters_by_entity_ids(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """Passes entity_ids filter to repository."""
        eid = uuid.uuid4()
        fake_wiki_repo.configure("get_summaries", [_make_wiki_summary_row(entity_id=eid)])

        result = await service.get_summaries(_NOVEL_ID, _USER_ID, entity_ids=[eid])

        assert fake_wiki_repo.call_count("get_summaries") == 1
        assert result.total == 1

    async def test_returns_empty_list(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """Returns empty list when no summaries exist."""
        fake_wiki_repo.configure("get_summaries", [])

        result = await service.get_summaries(_NOVEL_ID, _USER_ID, entity_ids=None)

        assert result.total == 0
        assert result.items == []


# ---------------------------------------------------------------------------
# Tests: get_wiki_index
# ---------------------------------------------------------------------------


class TestGetWikiIndex:
    """APIWikiService.get_wiki_index tests."""

    async def test_returns_index_with_counts(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """Returns WikiIndexResponse with correct status counts."""
        fake_wiki_repo.configure(
            "get_summaries",
            [
                _make_wiki_summary_row(status="fresh"),
                _make_wiki_summary_row(status="fresh"),
                _make_wiki_summary_row(status="stale"),
                _make_wiki_summary_row(status="pending"),
            ],
        )

        result: WikiIndexResponse = await service.get_wiki_index(_NOVEL_ID, _USER_ID)

        assert result.total_summaries == 4
        assert result.fresh_count == 2
        assert result.stale_count == 1
        assert result.pending_count == 1
        assert result.last_generated_at is not None

    async def test_empty_summaries(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """Empty summaries returns zero counts and None last_generated_at."""
        fake_wiki_repo.configure("get_summaries", [])

        result = await service.get_wiki_index(_NOVEL_ID, _USER_ID)

        assert result.total_summaries == 0
        assert result.fresh_count == 0
        assert result.stale_count == 0
        assert result.pending_count == 0
        assert result.last_generated_at is None

    async def test_last_generated_at_is_newest(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """last_generated_at returns the most recent generated_at."""
        older = datetime.now(UTC)
        newer = datetime.now(UTC)
        fake_wiki_repo.configure(
            "get_summaries",
            [
                _make_wiki_summary_row(generated_at=older),
                _make_wiki_summary_row(generated_at=newer),
            ],
        )

        result = await service.get_wiki_index(_NOVEL_ID, _USER_ID)

        assert result.last_generated_at == newer
