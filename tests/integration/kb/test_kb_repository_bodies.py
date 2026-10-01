"""Integration tests for ``KBRepository.get_bodies_by_ids`` — real PostgreSQL.

Deferred from the pydantic-ai-2.52 upgrade plan: the method is the ADR-090
rerank text fetcher (Decision 4) but shipped without an integration test.
Pins the batch-lookup contract the rerank stage relies on:

- Bodies come back as an ``entry_id -> body`` mapping for the requested ids
  (one batch SELECT — the fetcher seam, ADR-090 D4).
- Ids without a row — or with a NULL / empty body — are absent from the
  mapping: the rerank stage treats them as textless and keeps their
  first-stage ranking position, so empty text is never rerankable.
- Empty input short-circuits to ``{}`` without a query.

Fixture pattern follows the sibling repository test
``test_dismissed_repository.py`` (transaction-wrapped ``db_session``,
ORM-seeded User + Novel for the FK chain; entries via ``KBRepository.create``
as in ``test_kb_embedding_hooks.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from narrare.auth.models import User
from narrare.kb.models import KBEntry
from narrare.kb.repository import KBRepository
from narrare.novels.models import Novel

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fixtures + seeding helpers
# ---------------------------------------------------------------------------


async def _create_novel(session: AsyncSession) -> UUID:
    """Insert a minimal Novel (with a User) to satisfy FK constraints."""
    user = User(
        id=uuid4(),
        email=f"test-{uuid4().hex[:12]}@example.com",
        hashed_password="not-a-real-hash",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()

    novel = Novel(
        id=uuid4(),
        user_id=user.id,
        title="Rerank Bodies Novel",
    )
    session.add(novel)
    await session.flush()
    return novel.id


async def _create_entry(
    session: AsyncSession,
    novel_id: UUID,
    *,
    name: str,
    body: str | None,
) -> KBEntry:
    """Persist a KB entry with the given body and return it."""
    entry = KBEntry(
        novel_id=novel_id,
        entity_type="character",
        name=name,
        slug=name.lower().replace(" ", "-"),
        status="draft",
        body=body,
    )
    repo = KBRepository(session)
    return await repo.create(entry)


@pytest.fixture
async def repo(db_session: AsyncSession) -> KBRepository:
    return KBRepository(db_session)


@pytest.fixture
async def novel_id(db_session: AsyncSession) -> UUID:
    """Create a novel and return its ID."""
    return await _create_novel(db_session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetBodiesByIds:
    """Batch body lookup backing the ADR-090 rerank text fetcher."""

    async def test_returns_bodies_for_requested_entries(
        self,
        repo: KBRepository,
        db_session: AsyncSession,
        novel_id: UUID,
    ) -> None:
        """Bodies of the requested entries come back keyed by entry id."""
        first = await _create_entry(db_session, novel_id, name="Alice", body="Alice of Wonderland.")
        second = await _create_entry(db_session, novel_id, name="Bob", body="Bob the Builder.")

        bodies = await repo.get_bodies_by_ids([first.id, second.id])

        assert bodies == {first.id: "Alice of Wonderland.", second.id: "Bob the Builder."}

    async def test_excludes_null_body_entries_from_mapping(
        self,
        repo: KBRepository,
        db_session: AsyncSession,
        novel_id: UUID,
    ) -> None:
        """An entry with a NULL body is absent — NULL text is not rerankable."""
        with_body = await _create_entry(db_session, novel_id, name="Carol", body="real text")
        null_body = await _create_entry(db_session, novel_id, name="Dan", body=None)

        bodies = await repo.get_bodies_by_ids([with_body.id, null_body.id])

        assert bodies == {with_body.id: "real text"}

    async def test_excludes_empty_body_entries_from_mapping(
        self,
        repo: KBRepository,
        db_session: AsyncSession,
        novel_id: UUID,
    ) -> None:
        """An entry with an empty-string body is absent — matching the SQL filter."""
        with_body = await _create_entry(db_session, novel_id, name="Erin", body="real text")
        empty_body = await _create_entry(db_session, novel_id, name="Frank", body="")

        bodies = await repo.get_bodies_by_ids([with_body.id, empty_body.id])

        assert bodies == {with_body.id: "real text"}

    async def test_mixed_batch_returns_only_rerankable_bodies(
        self,
        repo: KBRepository,
        db_session: AsyncSession,
        novel_id: UUID,
    ) -> None:
        """One call over text/empty/NULL/missing ids yields only the text body."""
        with_body = await _create_entry(db_session, novel_id, name="Grace", body="real text")
        empty_body = await _create_entry(db_session, novel_id, name="Heidi", body="")
        null_body = await _create_entry(db_session, novel_id, name="Ivan", body=None)
        missing_id = uuid4()

        bodies = await repo.get_bodies_by_ids(
            [with_body.id, empty_body.id, null_body.id, missing_id]
        )

        assert bodies == {with_body.id: "real text"}

    async def test_empty_input_returns_empty_mapping(self, repo: KBRepository) -> None:
        """Empty candidate list short-circuits to ``{}`` (no query, per contract)."""
        assert await repo.get_bodies_by_ids([]) == {}
