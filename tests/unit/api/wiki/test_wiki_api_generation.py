"""Unit tests for APIWikiService — entity summary generation.

Tests ``generate_entity_summary`` with ownership checks, cross-novel
guards, and graceful degradation (RULE-11).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.wiki.service import APIWikiService
from narrare_core.shared.errors import ForbiddenError
from narrare_core.wiki.types import WikiEntityOutput
from tests.fakes import (
    FakeCoreWikiService,
    FakeKBRepository,
    FakeNovelRepository,
    FakeRelationshipRepository,
    FakeWikiRepository,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.uuid4()
_NOVEL_ID = uuid.uuid4()
_ENTITY_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity_output(**overrides: Any) -> WikiEntityOutput:
    """Create a WikiEntityOutput with test defaults."""
    return WikiEntityOutput(
        narrative_summary="A wise wizard who guards the Crystal of Eternity.",
        role_in_story="Mentor to the protagonist.",
        key_attributes=["wise", "ancient", "powerful"],
        relationships=[{"entity_id": str(uuid.uuid4()), "rel_type": "ally"}],
        character_arc="From isolation to mentorship.",
        **overrides,
    )


def _make_persisted_summary(**overrides: Any) -> dict[str, Any]:
    """Return a dict that WikiSummaryResponse.model_validate accepts."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "novel_id": _NOVEL_ID,
        "entity_id": _ENTITY_ID,
        "narrative_summary": "A wise wizard who guards the Crystal of Eternity.",
        "role_in_story": "Mentor to the protagonist.",
        "key_attributes": ["wise", "ancient", "powerful"],
        "relationships": [],
        "chapter_references": None,
        "character_arc": "From isolation to mentorship.",
        "status": "fresh",
        "version": 1,
        "generated_at": now,
        "refreshed_at": None,
    }
    data.update(overrides)
    return data


def _seed_novel(repo: FakeNovelRepository, *, user_id: uuid.UUID = _USER_ID) -> None:
    """Seed a test novel into the repository."""
    from narrare.novels.models import Novel

    repo.seed(Novel(id=_NOVEL_ID, user_id=user_id, writing_language="en", genre="Fantasy"))


def _seed_kb_entry(repo: FakeKBRepository) -> None:
    """Seed a test KB entry into the repository."""
    from narrare.kb.models import KBEntry

    repo.seed(
        KBEntry(
            id=_ENTITY_ID,
            novel_id=_NOVEL_ID,
            entity_type="character",
            name="Eldrin the Wise",
            body="Eldrin is an ancient wizard.",
        )
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_wiki_repo() -> FakeWikiRepository:
    repo = FakeWikiRepository()
    repo.configure("upsert_summary", _make_persisted_summary())
    return repo


@pytest.fixture()
def fake_kb_repo() -> FakeKBRepository:
    repo = FakeKBRepository()
    _seed_kb_entry(repo)
    return repo


@pytest.fixture()
def fake_novel_repo() -> FakeNovelRepository:
    repo = FakeNovelRepository()
    _seed_novel(repo)
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
# Tests: generate_entity_summary
# ---------------------------------------------------------------------------


class TestGenerateEntitySummary:
    """APIWikiService.generate_entity_summary tests."""

    async def test_happy_path(
        self,
        service: APIWikiService,
        fake_novel_repo: FakeNovelRepository,
        fake_kb_repo: FakeKBRepository,
        fake_core: FakeCoreWikiService,
        fake_wiki_repo: FakeWikiRepository,
        fake_relationship_repo: FakeRelationshipRepository,
    ) -> None:
        """Full flow: verify → load KB → build deps → generate → persist."""
        result = await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)

        fake_novel_repo.assert_called_once("get_by_id")
        fake_kb_repo.assert_called_once("get_by_id")
        fake_relationship_repo.assert_called_once("list_for_entry")
        fake_core.assert_called_once("generate_entity_summary")
        fake_wiki_repo.assert_called_once("upsert_summary")

        assert result is not None
        assert result.narrative_summary == "A wise wizard who guards the Crystal of Eternity."
        assert result.status == "fresh"

    async def test_system_mode_bypasses_ownership(
        self,
        system_service: APIWikiService,
        fake_novel_repo: FakeNovelRepository,
    ) -> None:
        """system_mode=True uses novel_repo.get() without ownership check."""
        result = await system_service.generate_entity_summary(
            _ENTITY_ID, _NOVEL_ID, uuid.UUID("00000000-0000-0000-0000-000000000000")
        )

        fake_novel_repo.assert_called_once("get")
        assert result is not None

    async def test_forbidden_error_propagates(
        self,
        service: APIWikiService,
        fake_novel_repo: FakeNovelRepository,
    ) -> None:
        """ForbiddenError from _verify_novel_ownership propagates."""
        fake_novel_repo._store.clear()

        with pytest.raises(ForbiddenError, match="You do not have access to this novel"):
            await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)

    async def test_entity_not_found_returns_none(
        self,
        service: APIWikiService,
        fake_kb_repo: FakeKBRepository,
        fake_core: FakeCoreWikiService,
    ) -> None:
        """Returns None when KB entity does not exist."""
        fake_kb_repo._store.clear()

        result = await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)

        assert result is None
        assert fake_core.call_count("generate_entity_summary") == 0

    async def test_entity_belongs_to_different_novel_returns_none(
        self,
        service: APIWikiService,
        fake_kb_repo: FakeKBRepository,
        fake_core: FakeCoreWikiService,
    ) -> None:
        """Returns None when entity's novel_id does not match (cross-novel access)."""
        from narrare.kb.models import KBEntry

        other_entry = KBEntry(id=_ENTITY_ID, novel_id=uuid.uuid4(), entity_type="character")
        fake_kb_repo._store[_ENTITY_ID] = other_entry

        result = await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)

        assert result is None
        assert fake_core.call_count("generate_entity_summary") == 0

    async def test_generation_failure_returns_none(
        self,
        service: APIWikiService,
        fake_core: FakeCoreWikiService,
        fake_wiki_repo: FakeWikiRepository,
    ) -> None:
        """Returns None when core generation returns None (graceful degradation)."""
        fake_core.configure("generate_entity_summary", None)

        result = await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)

        assert result is None
        assert fake_wiki_repo.call_count("upsert_summary") == 0

    async def test_exception_returns_none(
        self,
        service: APIWikiService,
        fake_core: FakeCoreWikiService,
    ) -> None:
        """Runtime error in generation is caught — returns None (RULE-11)."""
        fake_core.configure("generate_entity_summary", RuntimeError("LLM unavailable"))

        result = await service.generate_entity_summary(_ENTITY_ID, _NOVEL_ID, _USER_ID)

        assert result is None
