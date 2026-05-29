"""Integration tests for WikiRepository — CRUD operations.

Verifies upsert, lookup, and deletion for WikiSummary and
WikiChapterSummary against a real PostgreSQL database.
Uses the shared ``db_session`` fixture (rolled-back session) from the
integration conftest.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare.wiki.repository import WikiRepository
from narrare_core.wiki.types import WikiChapterOutput, WikiChapterSummaryData, WikiSummaryStatus

from ._helpers import (
    make_chapter_output,
    make_chapter_summary_data,
    make_entity_output,
    make_summary_data,
    seed_chapter,
    seed_kb_entry,
    seed_user_and_novel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestUpsertSummary:
    """WikiRepository.upsert_summary against real DB."""

    async def test_upsert_summary_creates_new(self, db_session: AsyncSession) -> None:
        """INSERT new WikiSummary, verify all fields persisted."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        summary_data = make_summary_data(novel_id, entity_id)
        output = make_entity_output()

        result = await repo.upsert_summary(summary_data, output)

        assert result.id is not None
        assert result.novel_id == novel_id
        assert result.entity_id == entity_id
        assert result.narrative_summary == "A brave warrior."
        assert result.role_in_story == "Protagonist"
        assert result.key_attributes == ["brave", "strong"]
        assert result.relationships is not None
        assert len(result.relationships) == 1
        assert result.character_arc == "Grows from farmer to hero."
        assert result.status == "fresh"
        assert result.version == 1
        assert result.content_hash == "abc123"

    async def test_upsert_summary_updates_existing(self, db_session: AsyncSession) -> None:
        """INSERT then UPDATE with ON CONFLICT, verify updated fields."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # First insert
        data_v1 = make_summary_data(novel_id, entity_id, content_hash="v1")
        output_v1 = make_entity_output(narrative_summary="Original summary.")
        await repo.upsert_summary(data_v1, output_v1)

        # Upsert with updated content
        data_v2 = make_summary_data(
            novel_id, entity_id, narrative_summary="Updated summary.", content_hash="v2", version=2
        )
        output_v2 = make_entity_output(narrative_summary="Updated summary.")
        result = await repo.upsert_summary(data_v2, output_v2)

        assert result.narrative_summary == "Updated summary."
        assert result.version == 2
        assert result.content_hash == "v2"
        assert result.generated_at is not None  # bumped by func.now()

        # Verify only one row exists
        all_rows = await repo.get_summaries(None, novel_id)
        assert len(all_rows) == 1


class TestUpsertChapterSummary:
    """WikiRepository.upsert_chapter_summary against real DB."""

    async def test_upsert_chapter_summary_creates_new(self, db_session: AsyncSession) -> None:
        """INSERT chapter summary, verify all fields persisted."""
        novel_id, _ = await seed_user_and_novel(db_session)
        chapter_id = await seed_chapter(db_session, novel_id)
        repo = WikiRepository(db_session)

        data = make_chapter_summary_data(chapter_id)
        output = make_chapter_output()

        result = await repo.upsert_chapter_summary(data, output)

        assert result.id is not None
        assert result.chapter_id == chapter_id
        assert result.narrative_summary == "The hero enters the forest."
        assert result.key_events == ["Hero enters forest", "Meets a spirit"]
        assert result.entities_involved is not None
        assert len(result.entities_involved) == 1
        assert result.themes == ["courage", "nature"]
        assert result.emotional_arc == "tense to relieved"
        assert result.status == "fresh"
        assert result.version == 1

    async def test_upsert_chapter_summary_updates_existing(self, db_session: AsyncSession) -> None:
        """ON CONFLICT update — second upsert overwrites first."""
        novel_id, _ = await seed_user_and_novel(db_session)
        chapter_id = await seed_chapter(db_session, novel_id)
        repo = WikiRepository(db_session)

        # First insert
        data_v1 = make_chapter_summary_data(chapter_id, wiki_prompt_version="1.0.0")
        output_v1 = make_chapter_output()
        await repo.upsert_chapter_summary(data_v1, output_v1)

        # Upsert with new content
        output_v2 = WikiChapterOutput(
            narrative_summary="Updated chapter summary.",
            key_events=["New event"],
            entities_involved=[],
            themes=["change"],
            emotional_arc="calm",
        )
        data_v2 = WikiChapterSummaryData(
            chapter_id=str(chapter_id),
            narrative_summary="Updated chapter summary.",
            key_events=["New event"],
            entities_involved=[],
            themes=["change"],
            emotional_arc="calm",
            chapter_content_hash="updated_hash",
            wiki_prompt_version="2.0.0",
            status=WikiSummaryStatus.FRESH,
            version=2,
        )
        result = await repo.upsert_chapter_summary(data_v2, output_v2)

        assert result.narrative_summary == "Updated chapter summary."
        assert result.version == 2
        assert result.wiki_prompt_version == "2.0.0"


class TestGetSummary:
    """WikiRepository.get_summary against real DB."""

    async def test_get_summary_found(self, db_session: AsyncSession) -> None:
        """get_summary returns existing summary."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        summary_data = make_summary_data(novel_id, entity_id)
        output = make_entity_output()
        await repo.upsert_summary(summary_data, output)

        result = await repo.get_summary(entity_id, novel_id)

        assert result is not None
        assert result.entity_id == entity_id
        assert result.narrative_summary == "A brave warrior."

    async def test_get_summary_not_found(self, db_session: AsyncSession) -> None:
        """get_summary returns None for non-existent entity."""
        novel_id, _ = await seed_user_and_novel(db_session)
        repo = WikiRepository(db_session)

        result = await repo.get_summary(uuid.uuid4(), novel_id)

        assert result is None


class TestGetSummariesBatch:
    """WikiRepository.get_summaries against real DB."""

    async def test_get_summaries_batch(self, db_session: AsyncSession) -> None:
        """Batch lookup with multiple entity IDs."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_a = await seed_kb_entry(db_session, novel_id)
        entity_b = await seed_kb_entry(db_session, novel_id)
        entity_c = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        for eid in (entity_a, entity_b, entity_c):
            data = make_summary_data(novel_id, eid, content_hash=str(eid)[:8])
            output = make_entity_output()
            await repo.upsert_summary(data, output)

        # Fetch only A and B
        results = await repo.get_summaries([entity_a, entity_b], novel_id)

        assert len(results) == 2
        returned_ids = {r.entity_id for r in results}
        assert entity_a in returned_ids
        assert entity_b in returned_ids
        assert entity_c not in returned_ids

    async def test_get_summaries_unfiltered(self, db_session: AsyncSession) -> None:
        """entity_ids=None returns all summaries for the novel."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_a = await seed_kb_entry(db_session, novel_id)
        entity_b = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        for eid in (entity_a, entity_b):
            data = make_summary_data(novel_id, eid, content_hash=str(eid)[:8])
            output = make_entity_output()
            await repo.upsert_summary(data, output)

        results = await repo.get_summaries(None, novel_id)

        assert len(results) == 2


class TestGetChapterSummary:
    """WikiRepository.get_chapter_summary against real DB."""

    async def test_get_chapter_summary_found(self, db_session: AsyncSession) -> None:
        """get_chapter_summary returns existing summary."""
        novel_id, _ = await seed_user_and_novel(db_session)
        chapter_id = await seed_chapter(db_session, novel_id)
        repo = WikiRepository(db_session)

        data = make_chapter_summary_data(chapter_id)
        output = make_chapter_output()
        await repo.upsert_chapter_summary(data, output)

        result = await repo.get_chapter_summary(chapter_id)

        assert result is not None
        assert result.chapter_id == chapter_id
        assert result.narrative_summary == "The hero enters the forest."

    async def test_get_chapter_summary_not_found(self, db_session: AsyncSession) -> None:
        """get_chapter_summary returns None for non-existent chapter."""
        repo = WikiRepository(db_session)

        result = await repo.get_chapter_summary(uuid.uuid4())

        assert result is None


class TestDeleteSummary:
    """WikiRepository.delete_summary against real DB."""

    async def test_delete_summary(self, db_session: AsyncSession) -> None:
        """Delete and verify gone."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        data = make_summary_data(novel_id, entity_id)
        output = make_entity_output()
        await repo.upsert_summary(data, output)

        # Verify it exists
        summary = await repo.get_summary(entity_id, novel_id)
        assert summary is not None

        # Delete
        await repo.delete_summary(entity_id)

        # Verify it's gone
        result = await repo.get_summary(entity_id, novel_id)
        assert result is None
