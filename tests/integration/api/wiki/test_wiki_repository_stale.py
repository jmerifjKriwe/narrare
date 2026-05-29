"""Integration tests for WikiRepository — staleness operations.

Verifies mark_stale, mark_all_stale, and mark_related_stale against
a real PostgreSQL database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.wiki.repository import WikiRepository
from narrare_core.wiki.types import WikiEntityOutput, WikiSummaryData, WikiSummaryStatus

from ._helpers import (
    make_entity_output,
    make_summary_data,
    seed_kb_entry,
    seed_user_and_novel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestMarkStale:
    """WikiRepository.mark_stale against real DB."""

    async def test_mark_stale(self, db_session: AsyncSession) -> None:
        """Mark specific entities stale, verify status."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_a = await seed_kb_entry(db_session, novel_id)
        entity_b = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        for eid in (entity_a, entity_b):
            data = make_summary_data(novel_id, eid, content_hash=str(eid)[:8])
            output = make_entity_output()
            await repo.upsert_summary(data, output)

        count = await repo.mark_stale([entity_a])

        assert count == 1

        # Verify A is stale, B is still fresh
        summary_a = await repo.get_summary(entity_a, novel_id)
        summary_b = await repo.get_summary(entity_b, novel_id)
        assert summary_a is not None
        assert summary_a.status == "stale"
        assert summary_b is not None
        assert summary_b.status == "fresh"


class TestMarkAllStale:
    """WikiRepository.mark_all_stale against real DB."""

    async def test_mark_all_stale_by_prompt_version(self, db_session: AsyncSession) -> None:
        """Mark all with old prompt version as stale."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_a = await seed_kb_entry(db_session, novel_id)
        entity_b = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # Entity A has old prompt version
        data_a = make_summary_data(
            novel_id,
            entity_a,
            content_hash="a",
            depends_on={"wiki_prompt_version": "1.0.0"},
        )
        output_a = make_entity_output()
        await repo.upsert_summary(data_a, output_a)

        # Entity B has current prompt version
        data_b = make_summary_data(
            novel_id,
            entity_b,
            content_hash="b",
            depends_on={"wiki_prompt_version": "2.0.0"},
        )
        output_b = make_entity_output()
        await repo.upsert_summary(data_b, output_b)

        # Mark stale where prompt_version != "2.0.0"
        count = await repo.mark_all_stale(novel_id, "2.0.0")

        assert count == 1

        summary_a = await repo.get_summary(entity_a, novel_id)
        summary_b = await repo.get_summary(entity_b, novel_id)
        assert summary_a is not None
        assert summary_a.status == "stale"
        assert summary_b is not None
        assert summary_b.status == "fresh"


class TestMarkRelatedStale:
    """WikiRepository.mark_related_stale against real DB.

    Uses JSONB containment ``@>`` on ``relationships`` array to find
    summaries that reference a given entity and marks them stale.
    """

    async def test_mark_related_stale(self, db_session: AsyncSession) -> None:
        """Create summaries with relationships referencing entity A,
        mark_related_stale(A), verify entity B's summary goes stale.
        """
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_a = await seed_kb_entry(db_session, novel_id)
        entity_b = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # Entity B's summary references Entity A in relationships
        rel = [{"entity_id": str(entity_a), "rel_type": "ally"}]
        output_b = WikiEntityOutput(
            narrative_summary="Entity B summary.",
            role_in_story="Ally",
            key_attributes=["loyal"],
            relationships=rel,
            character_arc=None,
        )
        data_b = WikiSummaryData(
            entity_id=str(entity_b),
            novel_id=str(novel_id),
            narrative_summary="Entity B summary.",
            role_in_story="Ally",
            key_attributes=["loyal"],
            relationships=rel,
            character_arc=None,
            depends_on={},
            status=WikiSummaryStatus.FRESH,
            version=1,
            content_hash="b",
        )
        await repo.upsert_summary(data_b, output_b)

        # Also create entity A's own summary (should NOT be affected)
        data_a = make_summary_data(novel_id, entity_a, content_hash="a")
        output_a = make_entity_output()
        await repo.upsert_summary(data_a, output_a)

        # Mark stale everything that references entity_a
        # The method uses JSONB containment: relationships @> [{"entity_id": str(entity_a)}]
        count = await repo.mark_related_stale(entity_a)

        # Entity B references entity A -> should be marked stale
        assert count >= 1

        summary_b = await repo.get_summary(entity_b, novel_id)
        assert summary_b is not None
        assert summary_b.status == "stale"
