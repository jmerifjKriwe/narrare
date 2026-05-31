"""Integration tests for Wiki schema — verifies tables exist after migration."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
import sqlalchemy
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestWikiSummariesSchema:
    """Verify wiki_summaries table columns after migration upgrade."""

    async def test_wiki_summaries_table_exists(self, db_session: AsyncSession) -> None:
        """wiki_summaries table should exist."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'wiki_summaries'"
                ")"
            )
        )
        assert result.scalar_one() is True

    async def test_wiki_summaries_has_narrative_summary_column(
        self, db_session: AsyncSession
    ) -> None:
        """wiki_summaries should have narrative_summary column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'wiki_summaries' AND column_name = 'narrative_summary'"
            )
        )
        assert result.scalar_one_or_none() == "narrative_summary"

    async def test_wiki_summaries_has_depends_on_column(self, db_session: AsyncSession) -> None:
        """wiki_summaries should have depends_on JSONB column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'wiki_summaries' AND column_name = 'depends_on'"
            )
        )
        assert result.scalar_one_or_none() == "depends_on"

    async def test_wiki_summaries_unique_constraint(self, db_session: AsyncSession) -> None:
        """wiki_summaries should have unique constraint on (novel_id, entity_id)."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'wiki_summaries' "
                "AND constraint_name = 'uq_wiki_summary_entity'"
            )
        )
        assert result.scalar_one_or_none() == "uq_wiki_summary_entity"

    async def test_wiki_summaries_status_check_constraint(self, db_session: AsyncSession) -> None:
        """wiki_summaries should have status check constraint."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'wiki_summaries' "
                "AND constraint_name = 'ck_wiki_summaries_status'"
            )
        )
        assert result.scalar_one_or_none() == "ck_wiki_summaries_status"

    async def test_wiki_summaries_accepts_valid_status_values(
        self, db_session: AsyncSession
    ) -> None:
        """wiki_summaries should accept all valid status values (pending, fresh, stale)."""
        from datetime import UTC, datetime

        # Satisfy FK chain: users → novels → kb_entries → wiki_summaries
        now = datetime.now(UTC)
        user_id = str(uuid.uuid4())
        novel_id = str(uuid.uuid4())
        await db_session.execute(
            sqlalchemy.text(
                "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
                "VALUES (:id, :email, :pwd, :now, :now)"
            ),
            {
                "id": user_id,
                "email": f"wiki-{uuid.uuid4().hex[:8]}@test.com",
                "pwd": "n/a",
                "now": now,
            },
        )
        await db_session.execute(
            sqlalchemy.text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, :now, :now)"
            ),
            {
                "id": novel_id,
                "user_id": user_id,
                "title": "Test Novel",
                "now": now,
            },
        )

        for i, status in enumerate(("pending", "fresh", "stale"), start=1):
            entity_id = str(uuid.uuid4())
            await db_session.execute(
                sqlalchemy.text(
                    "INSERT INTO kb_entries ("
                    "id, novel_id, entity_type, name, slug, created_at, updated_at"
                    ") "
                    "VALUES (:id, :novel_id, :type, :name, :slug, :now, :now)"
                ),
                {
                    "id": entity_id,
                    "novel_id": novel_id,
                    "type": "character",
                    "name": f"Test Entity {i}",
                    "slug": f"test-entity-{i}",
                    "now": now,
                },
            )
            stmt = sqlalchemy.text(
                "INSERT INTO wiki_summaries (id, novel_id, entity_id, narrative_summary, status) "
                "VALUES (:id, :novel_id, :entity_id, :summary, :status)"
            )
            await db_session.execute(
                stmt,
                {
                    "id": str(uuid.uuid4()),
                    "novel_id": novel_id,
                    "entity_id": entity_id,
                    "summary": "test",
                    "status": status,
                },
            )

    async def test_wiki_summaries_rejects_invalid_status(self, db_session: AsyncSession) -> None:
        """wiki_summaries status check constraint should reject invalid values."""
        from datetime import UTC, datetime

        # Satisfy FK chain: users → novels → kb_entries → wiki_summaries
        now = datetime.now(UTC)
        user_id = str(uuid.uuid4())
        novel_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())
        await db_session.execute(
            sqlalchemy.text(
                "INSERT INTO users (id, email, hashed_password, created_at, updated_at) "
                "VALUES (:id, :email, :pwd, :now, :now)"
            ),
            {
                "id": user_id,
                "email": f"wiki-{uuid.uuid4().hex[:8]}@test.com",
                "pwd": "n/a",
                "now": now,
            },
        )
        await db_session.execute(
            sqlalchemy.text(
                "INSERT INTO novels (id, user_id, title, created_at, updated_at) "
                "VALUES (:id, :user_id, :title, :now, :now)"
            ),
            {
                "id": novel_id,
                "user_id": user_id,
                "title": "Test Novel",
                "now": now,
            },
        )
        await db_session.execute(
            sqlalchemy.text(
                "INSERT INTO kb_entries ("
                "id, novel_id, entity_type, name, slug, created_at, updated_at"
                ") "
                "VALUES (:id, :novel_id, :type, :name, :slug, :now, :now)"
            ),
            {
                "id": entity_id,
                "novel_id": novel_id,
                "type": "character",
                "name": "Test Entity",
                "slug": "test-entity",
                "now": now,
            },
        )

        stmt = sqlalchemy.text(
            "INSERT INTO wiki_summaries (id, novel_id, entity_id, narrative_summary, status) "
            "VALUES (:id, :novel_id, :entity_id, :summary, :status)"
        )
        with pytest.raises(DBAPIError):
            await db_session.execute(
                stmt,
                {
                    "id": str(uuid.uuid4()),
                    "novel_id": novel_id,
                    "entity_id": entity_id,
                    "summary": "test",
                    "status": "invalid_status",
                },
            )


class TestWikiChapterSummariesSchema:
    """Verify wiki_chapter_summaries table columns after migration upgrade."""

    async def test_wiki_chapter_summaries_table_exists(self, db_session: AsyncSession) -> None:
        """wiki_chapter_summaries table should exist."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'wiki_chapter_summaries'"
                ")"
            )
        )
        assert result.scalar_one() is True

    async def test_wiki_chapter_summaries_has_narrative_summary_column(
        self, db_session: AsyncSession
    ) -> None:
        """wiki_chapter_summaries should have narrative_summary column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'wiki_chapter_summaries' "
                "AND column_name = 'narrative_summary'"
            )
        )
        assert result.scalar_one_or_none() == "narrative_summary"

    async def test_wiki_chapter_summaries_status_check_constraint(
        self, db_session: AsyncSession
    ) -> None:
        """wiki_chapter_summaries should have status check constraint."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'wiki_chapter_summaries' "
                "AND constraint_name = 'ck_wiki_chapter_status'"
            )
        )
        assert result.scalar_one_or_none() == "ck_wiki_chapter_status"

    async def test_wiki_chapter_summaries_chapter_id_unique(self, db_session: AsyncSession) -> None:
        """wiki_chapter_summaries.chapter_id should be unique."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT COUNT(*) FROM information_schema.table_constraints tc "
                "JOIN information_schema.constraint_column_usage ccu "
                "ON tc.constraint_name = ccu.constraint_name "
                "WHERE tc.table_name = 'wiki_chapter_summaries' "
                "AND tc.constraint_type = 'UNIQUE' "
                "AND ccu.column_name = 'chapter_id'"
            )
        )
        assert result.scalar_one() >= 1
