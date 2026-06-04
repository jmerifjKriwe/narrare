"""Unit tests for APIWikiService — summary queries, refresh, index, mark stale.

Tests ``get_summaries``, ``refresh_summary``, ``get_wiki_index``, and
``mark_all_stale`` with proper Fakes (RULE-TEST-01).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.wiki.service import APIWikiService
from tests.fakes import (
    FakeCoreWikiService,
    FakeKBRepository,
    FakeNovelRepository,
    FakeRelationshipRepository,
    FakeWikiRepository,
)

if TYPE_CHECKING:
    from narrare.wiki.schemas import WikiIndexResponse, WikiSummaryListResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_NOVEL_ID = uuid.uuid4()
_ENTITY_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity_output(**overrides: Any) -> Any:
    """Create a WikiEntityOutput with test defaults."""
    from narrare_core.wiki.types import WikiEntityOutput

    return WikiEntityOutput(
        narrative_summary="A wise wizard who guards the Crystal of Eternity.",
        role_in_story="Mentor to the protagonist.",
        key_attributes=["wise", "ancient", "powerful"],
        relationships=[{"entity_id": str(uuid.uuid4()), "rel_type": "ally"}],
        character_arc="From isolation to mentorship.",
        **overrides,
    )


def _make_wiki_summary_row(**overrides: Any) -> Any:
    """Return a WikiSummary instance (for get_summaries / get_summary)."""
    from narrare.wiki.models import WikiSummary

    kw: dict[str, Any] = {
        "id": uuid.uuid4(),
        "novel_id": _NOVEL_ID,
        "entity_id": uuid.uuid4(),
        "narrative_summary": "A brave warrior.",
        "role_in_story": "Protagonist",
        "key_attributes": ["brave", "strong"],
        "relationships": [],
        "chapter_references": None,
        "character_arc": None,
        "status": "fresh",
        "version": 1,
        "generated_at": datetime.now(UTC),
        "refreshed_at": None,
    }
    kw.update(overrides)
    return WikiSummary(**kw)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_wiki_repo() -> FakeWikiRepository:
    return FakeWikiRepository()


@pytest.fixture()
def fake_kb_repo() -> FakeKBRepository:
    from narrare.kb.models import KBEntry

    repo = FakeKBRepository()
    repo.seed(
        KBEntry(
            id=_ENTITY_ID,
            novel_id=_NOVEL_ID,
            entity_type="character",
            name="Eldrin the Wise",
            body="Eldrin is an ancient wizard.",
        )
    )
    return repo


@pytest.fixture()
def fake_novel_repo() -> FakeNovelRepository:
    from narrare.novels.models import Novel

    repo = FakeNovelRepository()
    repo.seed(Novel(id=_NOVEL_ID, user_id=_USER_ID, writing_language="en", genre="Fantasy"))
    return repo


@pytest.fixture()
def fake_relationship_repo() -> FakeRelationshipRepository:
    return FakeRelationshipRepository()


@pytest.fixture()
def fake_core() -> FakeCoreWikiService:
    svc = FakeCoreWikiService()
    svc.configure("generate_entity_summary", _make_entity_output())
    return svc


@pytest.fixture()
def service(
    fake_wiki_repo: FakeWikiRepository,
    fake_kb_repo: FakeKBRepository,
    fake_novel_repo: FakeNovelRepository,
    fake_relationship_repo: FakeRelationshipRepository,
    fake_core: FakeCoreWikiService,
) -> APIWikiService:
    """APIWikiService with all fake deps — system_mode=False."""
    return APIWikiService(
        session=AsyncMock(spec=AsyncSession),
        wiki_repo=fake_wiki_repo,
        kb_repo=fake_kb_repo,
        novel_repo=fake_novel_repo,
        relationship_repo=fake_relationship_repo,
        core_wiki_service=fake_core,
        chapter_wiki_service=None,
        system_mode=False,
    )


@pytest.fixture()
def system_service(
    fake_wiki_repo: FakeWikiRepository,
    fake_kb_repo: FakeKBRepository,
    fake_novel_repo: FakeNovelRepository,
    fake_relationship_repo: FakeRelationshipRepository,
    fake_core: FakeCoreWikiService,
) -> APIWikiService:
    """APIWikiService with system_mode=True (bypasses ownership checks)."""
    return APIWikiService(
        session=AsyncMock(spec=AsyncSession),
        wiki_repo=fake_wiki_repo,
        kb_repo=fake_kb_repo,
        novel_repo=fake_novel_repo,
        relationship_repo=fake_relationship_repo,
        core_wiki_service=fake_core,
        chapter_wiki_service=None,
        system_mode=True,
    )


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
