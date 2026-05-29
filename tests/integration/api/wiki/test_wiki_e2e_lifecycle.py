"""E2E integration tests for wiki lifecycle — staleness, queries, refresh.

Tests wiki staleness tracking, index/query operations, and refresh
pipeline through the full service → repository → DB stack.

Uses real DB (rolled-back session) with mocked core WikiServiceProtocol
to avoid real LLM calls while exercising all other layers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from narrare.wiki.repository import WikiRepository
from narrare_core.wiki.types import (
    WikiEntityOutput,
    WikiSummaryData,
    WikiSummaryStatus,
)

from ._helpers import (
    SYSTEM_USER,
    build_wiki_service,
    make_entity_output,
    make_summary_data,
    seed_kb_entry,
    seed_user_and_novel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ======================================================================
# 4. Staleness pipeline
# ======================================================================


class TestStalenessPipeline:
    """E2E: staleness tracking through service → repository → DB."""

    async def test_mark_all_stale_by_prompt_version(self, db_session: AsyncSession) -> None:
        """Different prompt versions → mark_all_stale → only old ones stale."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_old = await seed_kb_entry(db_session, novel_id)
        entity_new = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # Old prompt version — should be marked stale
        data_old = make_summary_data(
            novel_id,
            entity_old,
            content_hash="old",
            depends_on={"wiki_prompt_version": "1.0.0"},
        )
        await repo.upsert_summary(data_old, make_entity_output())

        # Current prompt version — should stay fresh
        data_new = make_summary_data(
            novel_id,
            entity_new,
            content_hash="new",
            depends_on={"wiki_prompt_version": "2.0.0"},
        )
        await repo.upsert_summary(data_new, make_entity_output())

        mock_core = AsyncMock()
        svc = build_wiki_service(db_session, core_wiki_service=mock_core)

        count = await svc.mark_all_stale(novel_id, SYSTEM_USER, prompt_version="2.0.0")

        assert count == 1

        old_summary = await repo.get_summary(entity_old, novel_id)
        new_summary = await repo.get_summary(entity_new, novel_id)
        assert old_summary is not None
        assert old_summary.status == "stale"
        assert new_summary is not None
        assert new_summary.status == "fresh"

    async def test_cross_entity_staleness_propagation(self, db_session: AsyncSession) -> None:
        """B references A → update A → B marked stale via mark_related_stale."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_a = await seed_kb_entry(db_session, novel_id)
        entity_b = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # B's summary references A in relationships
        rel_a = [{"entity_id": str(entity_a), "rel_type": "ally"}]
        output_b = WikiEntityOutput(
            narrative_summary="B summary.",
            role_in_story="Ally",
            key_attributes=["loyal"],
            relationships=rel_a,
        )
        data_b = WikiSummaryData(
            entity_id=str(entity_b),
            novel_id=str(novel_id),
            narrative_summary="B summary.",
            role_in_story="Ally",
            key_attributes=["loyal"],
            relationships=rel_a,
            status=WikiSummaryStatus.FRESH,
            version=1,
            content_hash="b",
        )
        await repo.upsert_summary(data_b, output_b)

        # A's own summary — should NOT be affected
        data_a = make_summary_data(novel_id, entity_a, content_hash="a")
        await repo.upsert_summary(data_a, make_entity_output())

        # Simulate: A was updated → mark everything referencing A as stale
        mock_core = AsyncMock()
        svc = build_wiki_service(db_session, core_wiki_service=mock_core)
        count = await svc.mark_related_stale(entity_a)

        assert count >= 1

        summary_b = await repo.get_summary(entity_b, novel_id)
        assert summary_b is not None
        assert summary_b.status == "stale"

        # A's own summary stays fresh (doesn't reference itself)
        summary_a = await repo.get_summary(entity_a, novel_id)
        assert summary_a is not None
        assert summary_a.status == "fresh"


# ======================================================================
# 5. Query pipeline
# ======================================================================


class TestQueryPipeline:
    """E2E: wiki query operations through service → repository."""

    async def test_get_summaries_returns_only_requested(self, db_session: AsyncSession) -> None:
        """Create 3 summaries, request 2 → only those returned."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_a = await seed_kb_entry(db_session, novel_id)
        entity_b = await seed_kb_entry(db_session, novel_id)
        entity_c = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        for eid in (entity_a, entity_b, entity_c):
            data = make_summary_data(novel_id, eid, content_hash=str(eid)[:8])
            await repo.upsert_summary(data, make_entity_output())

        mock_core = AsyncMock()
        svc = build_wiki_service(db_session, core_wiki_service=mock_core)

        result = await svc.get_summaries(novel_id, SYSTEM_USER, entity_ids=[entity_a, entity_b])

        assert result.total == 2
        returned_ids = {item.entity_id for item in result.items}
        assert entity_a in returned_ids
        assert entity_b in returned_ids
        assert entity_c not in returned_ids

    async def test_wiki_index_counts_correct(self, db_session: AsyncSession) -> None:
        """Mixed statuses → get_wiki_index → fresh/stale/pending counts correct."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_fresh = await seed_kb_entry(db_session, novel_id)
        entity_stale = await seed_kb_entry(db_session, novel_id)
        entity_pending = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # FRESH summary
        await repo.upsert_summary(
            make_summary_data(novel_id, entity_fresh, content_hash="f"),
            make_entity_output(),
        )

        # STALE summary
        data_stale = make_summary_data(
            novel_id, entity_stale, content_hash="s", status=WikiSummaryStatus.STALE
        )
        await repo.upsert_summary(data_stale, make_entity_output())

        # PENDING summary
        data_pending = make_summary_data(
            novel_id, entity_pending, content_hash="p", status=WikiSummaryStatus.PENDING
        )
        await repo.upsert_summary(data_pending, make_entity_output())

        mock_core = AsyncMock()
        svc = build_wiki_service(db_session, core_wiki_service=mock_core)

        index = await svc.get_wiki_index(novel_id, SYSTEM_USER)

        assert index.total_summaries == 3
        assert index.fresh_count == 1
        assert index.stale_count == 1
        assert index.pending_count == 1


# ======================================================================
# 6. Refresh pipeline
# ======================================================================


class TestRefreshPipeline:
    """E2E: wiki refresh operations — force regeneration vs. skip."""

    async def test_refresh_forces_regeneration(self, db_session: AsyncSession) -> None:
        """FRESH summary + force=True → new generation happens, summary updated."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # Pre-existing FRESH summary
        await repo.upsert_summary(
            make_summary_data(novel_id, entity_id, content_hash="v1"),
            make_entity_output(narrative_summary="Original summary."),
        )

        # Mock core to return updated output
        new_output = WikiEntityOutput(
            narrative_summary="Updated summary after refresh.",
            role_in_story="Hero",
            key_attributes=["refreshed"],
            relationships=[],
        )
        mock_core = AsyncMock()
        mock_core.generate_entity_summary = AsyncMock(return_value=new_output)

        svc = build_wiki_service(db_session, core_wiki_service=mock_core)

        result = await svc.refresh_summary(entity_id, novel_id, SYSTEM_USER, force=True)

        assert result.status == "fresh"
        assert result.summary_id is not None

        # Core was called — new generation happened
        mock_core.generate_entity_summary.assert_called_once()

        # Summary updated in DB
        persisted = await repo.get_summary(entity_id, novel_id)
        assert persisted is not None
        assert persisted.narrative_summary == "Updated summary after refresh."

    async def test_refresh_skips_when_fresh(self, db_session: AsyncSession) -> None:
        """FRESH summary + force=False → no new generation, early return."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # Pre-existing FRESH summary
        await repo.upsert_summary(
            make_summary_data(novel_id, entity_id, content_hash="v1"),
            make_entity_output(narrative_summary="Original summary."),
        )

        mock_core = AsyncMock()
        mock_core.generate_entity_summary = AsyncMock(return_value=make_entity_output())

        svc = build_wiki_service(db_session, core_wiki_service=mock_core)

        result = await svc.refresh_summary(entity_id, novel_id, SYSTEM_USER, force=False)

        assert result.status == "fresh"
        assert "already fresh" in result.message

        # Core was NOT called — no generation
        mock_core.generate_entity_summary.assert_not_called()

        # Summary unchanged in DB
        persisted = await repo.get_summary(entity_id, novel_id)
        assert persisted is not None
        assert persisted.narrative_summary == "Original summary."
