"""Shared infrastructure for APIWikiService tests.

Contains constants, helpers, and fixtures shared by
``test_wiki_api_generation.py`` and ``test_wiki_api_queries.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.wiki.service import APIWikiService
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_wiki_repo() -> FakeWikiRepository:
    """Fake WikiRepository."""
    repo = FakeWikiRepository()
    repo.configure("upsert_summary", _make_persisted_summary())
    return repo


@pytest.fixture()
def fake_kb_repo() -> FakeKBRepository:
    """Fake KBRepository."""
    from narrare.kb.models import KBEntry

    entry = KBEntry(
        id=_ENTITY_ID,
        novel_id=_NOVEL_ID,
        entity_type="character",
        name="Eldrin the Wise",
        body="Eldrin is an ancient wizard.",
    )
    repo = FakeKBRepository()
    repo.seed(entry)
    return repo


@pytest.fixture()
def fake_novel_repo() -> FakeNovelRepository:
    """Fake NovelRepository."""
    from narrare.novels.models import Novel

    novel = Novel(id=_NOVEL_ID, user_id=_USER_ID, writing_language="en", genre="Fantasy")
    repo = FakeNovelRepository()
    repo.seed(novel)
    return repo


@pytest.fixture()
def fake_relationship_repo() -> FakeRelationshipRepository:
    """Fake RelationshipRepository."""
    return FakeRelationshipRepository()


@pytest.fixture()
def fake_core() -> FakeCoreWikiService:
    """Fake core WikiServiceProtocol."""
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
    """APIWikiService with all fake deps — system_mode=False (user-facing)."""
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
