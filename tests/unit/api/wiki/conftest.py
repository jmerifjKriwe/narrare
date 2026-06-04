"""Shared fixtures, constants, and helpers for wiki API tests."""

import uuid
from datetime import UTC, datetime
from typing import Any
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


def _make_wiki_summary_row(**overrides: Any) -> Any:  # pyright: ignore[reportUnusedFunction]
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
