"""E2E integration tests for wiki generation pipeline — core generation.

Tests the complete lifecycle from service call to persisted result:
  entity → service → (mocked LLM) → repository → DB → verify.

Uses real DB (rolled-back session) with mocked core WikiServiceProtocol
to avoid real LLM calls while exercising all other layers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.wiki.chapter_service import ChapterWikiService
from narrare.wiki.listeners import WikiEventListener
from narrare.wiki.repository import WikiRepository
from narrare_core.events.types import DomainEvent, EventType
from narrare_core.wiki.types import WikiChapterOutput, WikiEntityOutput

from ._helpers import (
    SYSTEM_USER,
    build_wiki_service,
    make_entity_output,
    seed_chapter,
    seed_kb_entry,
    seed_user_and_novel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ======================================================================
# 1. Entity summary generation pipeline
# ======================================================================


class TestGenerateEntitySummary:
    """E2E: entity summary generation — service → repository → DB."""

    async def test_generate_entity_summary_persists_result(self, db_session: AsyncSession) -> None:
        """Full pipeline: create entity → generate → persist → verify fields."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)

        entity_output = WikiEntityOutput(
            narrative_summary="A fearless warrior who fights dragons.",
            role_in_story="Hero",
            key_attributes=["courageous", "strong"],
            relationships=[],
            character_arc="Farmer to dragon slayer.",
        )
        mock_core = AsyncMock()
        mock_core.generate_entity_summary = AsyncMock(return_value=entity_output)

        svc = build_wiki_service(db_session, core_wiki_service=mock_core)

        result = await svc.generate_entity_summary(entity_id, novel_id, SYSTEM_USER)

        assert result is not None
        assert result.entity_id == entity_id
        assert result.narrative_summary == "A fearless warrior who fights dragons."
        assert result.role_in_story == "Hero"
        assert result.key_attributes == ["courageous", "strong"]
        assert result.character_arc == "Farmer to dragon slayer."
        assert result.status == "fresh"

        # Verify persisted in DB via independent repo query
        wiki_repo = WikiRepository(db_session)
        persisted = await wiki_repo.get_summary(entity_id, novel_id)
        assert persisted is not None
        assert persisted.narrative_summary == "A fearless warrior who fights dragons."
        assert persisted.status == "fresh"
        assert persisted.role_in_story == "Hero"

    async def test_generate_entity_summary_graceful_degradation(
        self, db_session: AsyncSession
    ) -> None:
        """Core returns None (generation failure) → no summary persisted, no exception."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)

        mock_core = AsyncMock()
        mock_core.generate_entity_summary = AsyncMock(return_value=None)

        svc = build_wiki_service(db_session, core_wiki_service=mock_core)

        result = await svc.generate_entity_summary(entity_id, novel_id, SYSTEM_USER)

        assert result is None

        wiki_repo = WikiRepository(db_session)
        persisted = await wiki_repo.get_summary(entity_id, novel_id)
        assert persisted is None


# ======================================================================
# 2. Event-driven pipeline
# ======================================================================


class TestEventDrivenPipeline:
    """E2E: event → listener → task → service → repository → DB."""

    async def test_entity_update_triggers_wiki_sync_event(self, db_session: AsyncSession) -> None:
        """KB_ENTRY_UPDATED event → listener processes → summary persisted."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)

        entity_output = make_entity_output()
        mock_core = AsyncMock()
        mock_core.generate_entity_summary = AsyncMock(return_value=entity_output)

        svc = build_wiki_service(db_session, core_wiki_service=mock_core)
        listener = WikiEventListener(wiki_service_factory=lambda: svc)

        event = DomainEvent(
            event_type=EventType.KB_ENTRY_UPDATED,
            aggregate_id=entity_id,
            payload={"entity_id": str(entity_id), "novel_id": str(novel_id)},
        )

        await listener.on_kb_entry_updated(event)

        wiki_repo = WikiRepository(db_session)
        persisted = await wiki_repo.get_summary(entity_id, novel_id)
        assert persisted is not None
        assert persisted.narrative_summary == "A brave warrior."
        assert persisted.status == "fresh"


# ======================================================================
# 3. Chapter summary pipeline
# ======================================================================


class TestChapterSummaryPipeline:
    """E2E: chapter summary generation — ChapterWikiService → repo → DB."""

    async def test_chapter_summary_generation(self, db_session: AsyncSession) -> None:
        """Create chapter → generate summary → verify WikiChapterSummary persisted."""
        novel_id, _ = await seed_user_and_novel(db_session)
        chapter_id = await seed_chapter(db_session, novel_id)

        chapter_output = WikiChapterOutput(
            narrative_summary="The hero discovers a hidden cave.",
            key_events=["Discovery of cave", "Finding ancient artifact"],
            entities_involved=[],
            themes=["exploration", "mystery"],
            emotional_arc="curious to amazed",
        )
        mock_core = AsyncMock()
        mock_core.generate_chapter = AsyncMock(return_value=chapter_output)

        chapter_svc = ChapterWikiService(
            wiki_repo=WikiRepository(db_session),
            novel_repo=NovelRepository(db_session),
            chapter_repo=ChapterRepository(db_session),
            core_wiki_service=mock_core,
            system_mode=True,
        )

        result = await chapter_svc.generate_chapter_summary(chapter_id, novel_id, SYSTEM_USER)

        assert result is not None
        assert result.chapter_id == chapter_id
        assert result.narrative_summary == "The hero discovers a hidden cave."
        assert result.key_events == ["Discovery of cave", "Finding ancient artifact"]
        assert result.themes == ["exploration", "mystery"]
        assert result.status == "fresh"

        # Verify persisted via repo
        wiki_repo = WikiRepository(db_session)
        persisted = await wiki_repo.get_chapter_summary(chapter_id)
        assert persisted is not None
        assert persisted.narrative_summary == "The hero discovers a hidden cave."
        assert persisted.status == "fresh"
