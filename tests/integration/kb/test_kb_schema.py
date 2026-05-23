"""Integration tests for KB schema — verifies tables exist after migration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestKBEntriesSchema:
    """Verify kb_entries table columns after migration upgrade."""

    async def test_kb_entries_table_exists(self, db_session: AsyncSession) -> None:
        """kb_entries table should exist."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'kb_entries'"
                ")"
            )
        )
        assert result.scalar_one() is True

    async def test_kb_entries_has_entity_type_column(self, db_session: AsyncSession) -> None:
        """kb_entries should have entity_type column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'kb_entries' AND column_name = 'entity_type'"
            )
        )
        assert result.scalar_one_or_none() == "entity_type"

    async def test_kb_entries_has_metadata_column(self, db_session: AsyncSession) -> None:
        """kb_entries should have metadata JSONB column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'kb_entries' AND column_name = 'metadata'"
            )
        )
        assert result.scalar_one_or_none() == "metadata"

    async def test_kb_entries_has_slug_column(self, db_session: AsyncSession) -> None:
        """kb_entries should have slug column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'kb_entries' AND column_name = 'slug'"
            )
        )
        assert result.scalar_one_or_none() == "slug"

    async def test_kb_entries_novel_slug_unique_constraint(self, db_session: AsyncSession) -> None:
        """kb_entries should have unique constraint on (novel_id, slug)."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'kb_entries' "
                "AND constraint_name = 'uq_kb_entries_novel_slug'"
            )
        )
        assert result.scalar_one_or_none() == "uq_kb_entries_novel_slug"


class TestKBRelationshipsSchema:
    """Verify kb_relationships table columns after migration upgrade."""

    async def test_kb_relationships_table_exists(self, db_session: AsyncSession) -> None:
        """kb_relationships table should exist."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'kb_relationships'"
                ")"
            )
        )
        assert result.scalar_one() is True

    async def test_kb_relationships_has_rel_type_column(self, db_session: AsyncSession) -> None:
        """kb_relationships should have rel_type column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'kb_relationships' "
                "AND column_name = 'rel_type'"
            )
        )
        assert result.scalar_one_or_none() == "rel_type"

    async def test_kb_relationships_unique_constraint(self, db_session: AsyncSession) -> None:
        """kb_relationships should have unique constraint on source/target/type."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'kb_relationships' "
                "AND constraint_name = 'uq_kb_relationships_unique'"
            )
        )
        assert result.scalar_one_or_none() == "uq_kb_relationships_unique"

    async def test_kb_relationships_no_self_ref_check(self, db_session: AsyncSession) -> None:
        """kb_relationships should have self-reference check constraint."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'kb_relationships' "
                "AND constraint_name = 'ck_kb_relationships_no_self_ref'"
            )
        )
        assert result.scalar_one_or_none() == "ck_kb_relationships_no_self_ref"
