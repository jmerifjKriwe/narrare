"""Shared seed helpers and data builders for wiki integration tests.

Provides DB seeding functions (insert users, novels, KB entries, chapters),
factory helpers for WikiSummaryData, WikiEntityOutput, etc., and
APIWikiService builder with mocked core service.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import sqlalchemy

from narrare.kb.relationship_repository import RelationshipRepository
from narrare.kb.repository import KBRepository
from narrare.novels.repository import NovelRepository
from narrare.wiki.repository import WikiRepository
from narrare.wiki.service import APIWikiService
from narrare_core.wiki.types import (
    WikiChapterOutput,
    WikiChapterSummaryData,
    WikiEntityOutput,
    WikiSummaryData,
    WikiSummaryStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

SYSTEM_USER = uuid.UUID("00000000-0000-0000-0000-000000000000")


# ======================================================================
# DB seeding helpers
# ======================================================================


async def seed_user_and_novel(
    db_session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a user and novel, return (novel_id, user_id)."""
    user_id = uuid.uuid4()
    novel_id = uuid.uuid4()

    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
            "VALUES (:id, :email, 'fake_hash', now(), now())"
        ),
        {"id": str(user_id), "email": f"test-wiki-{user_id.hex[:8]}@example.com"},
    )

    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
            "VALUES (:id, :user_id, 'Test Novel', now(), now())"
        ),
        {"id": str(novel_id), "user_id": str(user_id)},
    )
    await db_session.flush()
    return novel_id, user_id


async def seed_kb_entry(
    db_session: AsyncSession,
    novel_id: uuid.UUID,
    *,
    name: str | None = None,
) -> uuid.UUID:
    """Insert a KB entry and return its ID."""
    entry_id = uuid.uuid4()
    entry_name = name or f"Entity-{entry_id.hex[:8]}"
    slug = entry_name.lower().replace(" ", "-")
    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO kb_entries "
            "(id, novel_id, entity_type, name, slug, status, created_at, updated_at) "
            "VALUES (:id, :novel_id, 'character', :name, :slug, 'draft', now(), now())"
        ),
        {"id": str(entry_id), "novel_id": str(novel_id), "name": entry_name, "slug": slug},
    )
    await db_session.flush()
    return entry_id


async def seed_chapter(
    db_session: AsyncSession,
    novel_id: uuid.UUID,
) -> uuid.UUID:
    """Insert a chapter and return its ID."""
    chapter_id = uuid.uuid4()
    await db_session.execute(
        sqlalchemy.text(
            "INSERT INTO chapters "
            "(id, novel_id, title, position, word_count, status, created_at, updated_at) "
            "VALUES (:id, :novel_id, 'Test Chapter', 0, 100, 'final', now(), now())"
        ),
        {"id": str(chapter_id), "novel_id": str(novel_id)},
    )
    await db_session.flush()
    return chapter_id


# ======================================================================
# Data factory helpers
# ======================================================================


def make_summary_data(
    novel_id: uuid.UUID,
    entity_id: uuid.UUID,
    *,
    narrative_summary: str = "A brave warrior.",
    depends_on: dict[str, Any] | None = None,
    status: WikiSummaryStatus = WikiSummaryStatus.FRESH,
    content_hash: str = "abc123",
    version: int = 1,
) -> WikiSummaryData:
    """Create WikiSummaryData for testing."""
    return WikiSummaryData(
        entity_id=str(entity_id),
        novel_id=str(novel_id),
        narrative_summary=narrative_summary,
        role_in_story="Protagonist",
        key_attributes=["brave", "strong"],
        relationships=[{"entity_id": str(uuid.uuid4()), "rel_type": "ally"}],
        character_arc="Grows from farmer to hero.",
        depends_on=depends_on if depends_on is not None else {},
        status=status,
        version=version,
        content_hash=content_hash,
    )


def make_entity_output(
    *,
    narrative_summary: str = "A brave warrior.",
    relationships: list[dict[str, Any]] | None = None,
) -> WikiEntityOutput:
    """Create WikiEntityOutput for testing."""
    return WikiEntityOutput(
        narrative_summary=narrative_summary,
        role_in_story="Protagonist",
        key_attributes=["brave", "strong"],
        relationships=relationships or [{"entity_id": str(uuid.uuid4()), "rel_type": "ally"}],
        character_arc="Grows from farmer to hero.",
    )


def make_chapter_summary_data(
    chapter_id: uuid.UUID,
    *,
    status: WikiSummaryStatus = WikiSummaryStatus.FRESH,
    wiki_prompt_version: str = "1.0.0",
) -> WikiChapterSummaryData:
    """Create WikiChapterSummaryData for testing."""
    return WikiChapterSummaryData(
        chapter_id=str(chapter_id),
        narrative_summary="The hero enters the forest.",
        key_events=["Hero enters forest", "Meets a spirit"],
        entities_involved=[{"entity_id": str(uuid.uuid4()), "role": "protagonist"}],
        themes=["courage", "nature"],
        emotional_arc="tense to relieved",
        chapter_content_hash="def456",
        wiki_prompt_version=wiki_prompt_version,
        status=status,
    )


def make_chapter_output() -> WikiChapterOutput:
    """Create WikiChapterOutput for testing."""
    return WikiChapterOutput(
        narrative_summary="The hero enters the forest.",
        key_events=["Hero enters forest", "Meets a spirit"],
        entities_involved=[{"entity_id": str(uuid.uuid4()), "role": "protagonist"}],
        themes=["courage", "nature"],
        emotional_arc="tense to relieved",
    )


# ======================================================================
# Service builder
# ======================================================================


def build_wiki_service(
    db_session: AsyncSession,
    *,
    core_wiki_service: Any,
    system_mode: bool = True,
) -> APIWikiService:
    """Build APIWikiService with real repos and mocked core service.

    Uses real DB-backed repositories for KB, novel, and relationship
    operations. Only the core ``WikiServiceProtocol`` (LLM layer) is mocked.
    """
    return APIWikiService(
        session=db_session,
        wiki_repo=WikiRepository(db_session),
        kb_repo=KBRepository(db_session),
        novel_repo=NovelRepository(db_session),
        relationship_repo=RelationshipRepository(db_session),
        core_wiki_service=core_wiki_service,
        system_mode=system_mode,
    )
