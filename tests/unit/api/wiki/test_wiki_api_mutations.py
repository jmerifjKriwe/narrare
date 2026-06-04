"""Unit tests for APIWikiService — summary refresh and mark stale.

Tests ``refresh_summary`` and ``mark_all_stale`` with proper Fakes (RULE-TEST-01).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .conftest import _ENTITY_ID, _NOVEL_ID, _USER_ID, _make_wiki_summary_row

if TYPE_CHECKING:
    from narrare.wiki.service import APIWikiService
    from tests.fakes import FakeCoreWikiService, FakeWikiRepository

# ---------------------------------------------------------------------------
# Tests: refresh_summary
# ---------------------------------------------------------------------------


class TestRefreshSummary:
    """APIWikiService.refresh_summary tests."""

    async def test_refresh_with_force(
        self,
        service: APIWikiService,
        fake_core: FakeCoreWikiService,
    ) -> None:
        """force=True always regenerates, ignoring existing status."""
        result = await service.refresh_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID, force=True)

        assert fake_core.call_count("generate_entity_summary") >= 1
        assert result is not None
        assert result.status == "fresh"
        assert result.message == "Summary refreshed successfully."

    async def test_skips_when_already_fresh(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
        fake_core: FakeCoreWikiService,
    ) -> None:
        """Without force, returns early when summary is already fresh."""
        fake_wiki_repo.configure("get_summary", _make_wiki_summary_row(status="fresh"))

        result = await service.refresh_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID, force=False)

        assert fake_core.call_count("generate_entity_summary") == 0
        assert result.status == "fresh"
        assert "already fresh" in result.message

    async def test_regenerates_when_stale(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
        fake_core: FakeCoreWikiService,
    ) -> None:
        """Without force, regenerates when existing summary is stale."""
        fake_wiki_repo.configure("get_summary", _make_wiki_summary_row(status="stale"))

        result = await service.refresh_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID, force=False)

        assert fake_core.call_count("generate_entity_summary") >= 1
        assert result.status == "fresh"

    async def test_generation_failure_returns_error_status(
        self,
        service: APIWikiService,
        fake_core: FakeCoreWikiService,
    ) -> None:
        """When generation returns None, returns error status."""
        fake_core.configure("generate_entity_summary", None)

        result = await service.refresh_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID, force=True)

        assert result.status == "error"
        assert "failed" in result.message.lower()


# ---------------------------------------------------------------------------
# Tests: mark_all_stale
# ---------------------------------------------------------------------------


class TestMarkAllStale:
    """APIWikiService.mark_all_stale tests."""

    async def test_marks_stale_and_returns_count(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """Returns count from repository mark_all_stale."""
        fake_wiki_repo.configure("mark_all_stale", 7)

        count = await service.mark_all_stale(_NOVEL_ID, _USER_ID, prompt_version="2.0.0")

        assert count == 7

    async def test_marks_stale_without_prompt_version(
        self,
        service: APIWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """Works with default prompt_version (empty string)."""
        count = await service.mark_all_stale(_NOVEL_ID, _USER_ID)

        assert count == 0
