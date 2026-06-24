"""CR-AUFG-07-19 — ``PromptHistoryRepository`` integration tests.

The repository owns SQLAlchemy queries only (RULE-06).  These tests exercise
it against the migrated ``prompt_revisions`` table via the rolled-back
``db_session`` fixture.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from narrare.auth.models import User
from narrare.prompts.models import PromptRevision
from narrare.prompts.repository import PromptHistoryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

PROMPT_ID = "writing/en/new_chapter"
SCOPE = "project"


def _hash(n: int) -> str:
    return f"{n:064d}"[-64:]


async def _make_user(db_session: AsyncSession, user_id: uuid.UUID) -> User:
    """Insert a minimal User row to satisfy the actor_id FK."""
    user = User(
        id=user_id,
        email=f"repo-{user_id}@example.com",
        hashed_password="not-a-real-hash",
    )
    db_session.add(user)
    await db_session.flush()
    return user


_BASE_TS = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


async def _seed(
    db_session: AsyncSession,
    prompt_id: str,
    *,
    scope: str = SCOPE,
    count: int,
    base: int = 0,
) -> list[uuid.UUID]:
    """Insert ``count`` revisions with explicit, monotonically increasing
    ``created_at`` values.

    PostgreSQL ``now()`` equals transaction-start time, so every row inserted
    inside a single test transaction would otherwise share the same
    ``created_at`` and defeat ORDER BY tests.  Seeding with explicit timestamps
    isolates the repository query logic from that quirk (each production save
    is its own transaction and does not suffer from it).
    """
    ids: list[uuid.UUID] = []
    for i in range(count):
        rev = PromptRevision(
            prompt_id=prompt_id,
            scope=scope,
            content=f"content-{base + i}",
            content_hash=_hash(base + i),
            source="save",
            created_at=_BASE_TS + timedelta(seconds=base + i),
        )
        db_session.add(rev)
        await db_session.flush()
        ids.append(rev.id)
    return ids


@pytest.fixture
def repo(db_session: AsyncSession) -> PromptHistoryRepository:
    return PromptHistoryRepository(db_session)


class TestInsertAndGet:
    async def test_insert_and_get_round_trip(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        """insert_revision persists; get_revision reads the row back."""
        actor = await _make_user(db_session, uuid.uuid4())
        rev = await repo.insert_revision(
            PROMPT_ID,
            SCOPE,
            content="hello",
            content_hash=_hash(1),
            actor_id=actor.id,
            source="save",
            change_reason="initial",
        )
        assert rev.id is not None
        assert rev.content_hash == _hash(1)

        fetched = await repo.get_revision(rev.id)
        assert fetched is not None
        assert fetched.content == "hello"
        assert fetched.change_reason == "initial"

    async def test_get_revision_returns_none_when_missing(
        self, repo: PromptHistoryRepository
    ) -> None:
        assert await repo.get_revision(uuid.uuid4()) is None


class TestListAndCount:
    async def test_list_returns_newest_first(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        """list_revisions orders by created_at DESC (newest first)."""
        await _seed(db_session, PROMPT_ID, count=3)

        rows = await repo.list_revisions(PROMPT_ID, SCOPE, limit=50, offset=0)
        assert len(rows) == 3
        # Newest (highest index) should be first.
        assert rows[0].content == "content-2"
        assert rows[2].content == "content-0"

    async def test_list_respects_limit_and_offset(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        await _seed(db_session, PROMPT_ID, count=5)

        page = await repo.list_revisions(PROMPT_ID, SCOPE, limit=2, offset=1)
        assert len(page) == 2
        # offset=1 skips the newest (content-4), so page is [content-3, content-2].
        assert page[0].content == "content-3"
        assert page[1].content == "content-2"

    async def test_list_scoped_to_prompt_and_scope(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        """list_revisions filters by (prompt_id, scope)."""
        await _seed(db_session, PROMPT_ID, scope="project", count=2)
        await _seed(db_session, PROMPT_ID, scope="user", count=1)
        await _seed(db_session, "other/en/mode", scope="project", count=1)

        project_rows = await repo.list_revisions(PROMPT_ID, "project", limit=50, offset=0)
        assert len(project_rows) == 2

    async def test_count_matches_inserts(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        await _seed(db_session, PROMPT_ID, count=4)
        assert await repo.count(PROMPT_ID, SCOPE) == 4

    async def test_count_is_scoped(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        await _seed(db_session, PROMPT_ID, scope="project", count=3)
        await _seed(db_session, PROMPT_ID, scope="user", count=2)
        assert await repo.count(PROMPT_ID, "project") == 3
        assert await repo.count(PROMPT_ID, "user") == 2


class TestGetLatest:
    async def test_get_latest_returns_most_recent(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        await _seed(db_session, PROMPT_ID, count=3)
        latest = await repo.get_latest_revision(PROMPT_ID, SCOPE)
        assert latest is not None
        assert latest.content == "content-2"

    async def test_get_latest_returns_none_when_empty(self, repo: PromptHistoryRepository) -> None:
        assert await repo.get_latest_revision(PROMPT_ID, SCOPE) is None


class TestDeleteHistory:
    async def test_delete_returns_count_and_clears_rows(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        await _seed(db_session, PROMPT_ID, count=3)
        deleted = await repo.delete_history(PROMPT_ID, SCOPE)
        assert deleted == 3
        assert await repo.count(PROMPT_ID, SCOPE) == 0

    async def test_delete_is_scoped(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        """delete_history only affects the given scope."""
        await _seed(db_session, PROMPT_ID, scope="project", count=2)
        await _seed(db_session, PROMPT_ID, scope="user", count=1)

        deleted = await repo.delete_history(PROMPT_ID, "project")
        assert deleted == 2
        assert await repo.count(PROMPT_ID, "project") == 0
        assert await repo.count(PROMPT_ID, "user") == 1

    async def test_delete_returns_zero_when_empty(self, repo: PromptHistoryRepository) -> None:
        assert await repo.delete_history(PROMPT_ID, SCOPE) == 0


class TestEnforceRetention:
    async def test_enforce_keeps_only_n_newest(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        """enforce_retention deletes oldest rows beyond ``keep``."""
        await _seed(db_session, PROMPT_ID, count=5)
        deleted = await repo.enforce_retention(PROMPT_ID, SCOPE, keep=2)
        assert deleted == 3
        assert await repo.count(PROMPT_ID, SCOPE) == 2
        remaining = await repo.list_revisions(PROMPT_ID, SCOPE, limit=50, offset=0)
        # The two newest survive (content-4, content-3).
        assert {r.content for r in remaining} == {"content-4", "content-3"}

    async def test_enforce_noop_when_under_limit(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        await _seed(db_session, PROMPT_ID, count=3)
        deleted = await repo.enforce_retention(PROMPT_ID, SCOPE, keep=100)
        assert deleted == 0
        assert await repo.count(PROMPT_ID, SCOPE) == 3

    async def test_enforce_is_scoped(
        self, repo: PromptHistoryRepository, db_session: AsyncSession
    ) -> None:
        """enforce_retention only prunes the given scope."""
        await _seed(db_session, PROMPT_ID, scope="project", count=4)
        await _seed(db_session, PROMPT_ID, scope="user", count=4)

        deleted = await repo.enforce_retention(PROMPT_ID, "project", keep=1)
        assert deleted == 3
        assert await repo.count(PROMPT_ID, "project") == 1
        # user scope untouched.
        assert await repo.count(PROMPT_ID, "user") == 4
