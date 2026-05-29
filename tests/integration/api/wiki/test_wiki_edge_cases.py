"""Edge-case integration tests for the wiki generation pipeline.

Tests boundary conditions, failure modes, debounce, and cascade behavior
against a real PostgreSQL database. Uses mocked LLM (core WikiServiceProtocol).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import sqlalchemy

from narrare.kb.relationship_repository import RelationshipRepository
from narrare.kb.repository import KBRepository
from narrare.novels.repository import NovelRepository
from narrare.wiki.listeners import WikiEventListener
from narrare.wiki.repository import WikiRepository
from narrare.wiki.service import APIWikiService
from narrare_core.events.types import DomainEvent, EventType
from narrare_core.wiki.types import (
    WikiEntityOutput,
    WikiSummaryStatus,
)

from ._helpers import (
    make_entity_output,
    make_summary_data,
    seed_kb_entry,
    seed_user_and_novel,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_SYSTEM_USER = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _build_service(
    db_session: AsyncSession,
    *,
    core_wiki_service: Any,
    system_mode: bool = True,
) -> APIWikiService:
    """Build APIWikiService with real repos and mocked core service."""
    return APIWikiService(
        session=db_session,
        wiki_repo=WikiRepository(db_session),
        kb_repo=KBRepository(db_session),
        novel_repo=NovelRepository(db_session),
        relationship_repo=RelationshipRepository(db_session),
        core_wiki_service=core_wiki_service,
        system_mode=system_mode,
    )


# ======================================================================
# Generation failure edge cases
# ======================================================================


class TestGenerationFailureEdgeCases:
    """Edge cases around generation failures and partial state."""

    async def test_generation_failure_leaves_pending(self, db_session: AsyncSession) -> None:
        """PENDING summary + core returns None → PENDING status preserved.

        A pre-existing PENDING summary should NOT be overwritten or changed
        to STALE when generation fails. It stays PENDING so the retry
        mechanism can pick it up later.
        """
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # Pre-create a PENDING summary (e.g. from a previous enqueue)
        pending_data = make_summary_data(
            novel_id,
            entity_id,
            content_hash="pending-v1",
            status=WikiSummaryStatus.PENDING,
            narrative_summary="",
        )
        pending_output = WikiEntityOutput(
            narrative_summary="",
            key_attributes=[],
            relationships=[],
        )
        await repo.upsert_summary(pending_data, pending_output)

        # Verify it's PENDING before generation attempt
        before = await repo.get_summary(entity_id, novel_id)
        assert before is not None
        assert before.status == "pending"

        # Core returns None (generation failure)
        mock_core = AsyncMock()
        mock_core.generate_entity_summary = AsyncMock(return_value=None)

        svc = _build_service(db_session, core_wiki_service=mock_core)

        result = await svc.generate_entity_summary(entity_id, novel_id, _SYSTEM_USER)

        assert result is None

        # PENDING summary should remain unchanged
        after = await repo.get_summary(entity_id, novel_id)
        assert after is not None
        assert after.status == "pending"

    async def test_entity_with_no_body(self, db_session: AsyncSession) -> None:
        """Entity with empty/missing body → graceful handling, summary generated.

        The service converts None body to "" via ``entity.body or ""``
        in _build_generation_deps. Generation should succeed without errors.
        """
        novel_id, _ = await seed_user_and_novel(db_session)
        # seed_kb_entry does NOT set body → body is NULL in DB
        entity_id = await seed_kb_entry(db_session, novel_id)

        entity_output = WikiEntityOutput(
            narrative_summary="An entity with no description yet.",
            role_in_story="Unknown",
            key_attributes=["undefined"],
            relationships=[],
        )
        mock_core = AsyncMock()
        mock_core.generate_entity_summary = AsyncMock(return_value=entity_output)

        svc = _build_service(db_session, core_wiki_service=mock_core)

        result = await svc.generate_entity_summary(entity_id, novel_id, _SYSTEM_USER)

        # Should succeed — no crash from None body
        assert result is not None
        assert result.narrative_summary == "An entity with no description yet."
        assert result.status == "fresh"

        # Verify persisted
        repo = WikiRepository(db_session)
        persisted = await repo.get_summary(entity_id, novel_id)
        assert persisted is not None
        assert persisted.status == "fresh"


# ======================================================================
# Listener edge cases
# ======================================================================


class TestListenerEdgeCases:
    """Edge cases for WikiEventListener behavior."""

    async def test_rapid_updates_debounced(self, db_session: AsyncSession) -> None:
        """Two rapid events for same entity → second is debounced, factory called once."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)

        entity_output = make_entity_output()
        mock_core = AsyncMock()
        mock_core.generate_entity_summary = AsyncMock(return_value=entity_output)

        svc = _build_service(db_session, core_wiki_service=mock_core)

        factory_calls = 0

        def tracking_factory() -> APIWikiService:
            nonlocal factory_calls
            factory_calls += 1
            return svc

        listener = WikiEventListener(wiki_service_factory=tracking_factory)

        event = DomainEvent(
            event_type=EventType.KB_ENTRY_UPDATED,
            aggregate_id=entity_id,
            payload={"entity_id": str(entity_id), "novel_id": str(novel_id)},
        )

        # First event → processed (factory called for generate + mark_related_stale)
        await listener.on_kb_entry_updated(event)
        first_call_count = factory_calls

        # Second event immediately → debounced
        await listener.on_kb_entry_updated(event)

        # Factory was NOT called again for the debounced event
        assert factory_calls == first_call_count
        assert factory_calls > 0  # First event did trigger processing

        # Only one summary exists (not duplicated)
        repo = WikiRepository(db_session)
        summaries = await repo.get_summaries(None, novel_id)
        assert len(summaries) == 1


# ======================================================================
# Cascade edge cases
# ======================================================================


class TestCascadeEdgeCases:
    """Edge cases for FK cascade behavior."""

    async def test_delete_entity_cascades_to_wiki(self, db_session: AsyncSession) -> None:
        """Delete KB entry → wiki summary deleted via CASCADE FK."""
        novel_id, _ = await seed_user_and_novel(db_session)
        entity_id = await seed_kb_entry(db_session, novel_id)
        repo = WikiRepository(db_session)

        # Create wiki summary for entity
        await repo.upsert_summary(
            make_summary_data(novel_id, entity_id, content_hash="cascade-test"),
            make_entity_output(),
        )

        # Verify summary exists
        summary = await repo.get_summary(entity_id, novel_id)
        assert summary is not None

        # Delete the KB entry via raw SQL (triggers CASCADE)
        await db_session.execute(
            sqlalchemy.text("DELETE FROM kb_entries WHERE id = :id"),
            {"id": str(entity_id)},
        )
        await db_session.flush()

        # Wiki summary should be gone (CASCADE)
        remaining = await repo.get_summary(entity_id, novel_id)
        assert remaining is None
