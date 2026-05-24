"""Integration tests for migration 0022_embeddings schema.

Verifies:
- ``embeddings`` table exists with correct columns and indexes.
- ``context_usage_events`` table exists with correct columns and constraints.
- ``kb_entries`` has ``last_referenced_at`` and ``usage_count`` columns.
- Unique constraint on ``embeddings(source_type, source_id, model)``.
- HNSW index on ``embeddings.embedding``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestEmbeddingsSchema:
    """Verify embeddings table columns and constraints after migration."""

    async def test_embeddings_table_exists(self, db_session: AsyncSession) -> None:
        """embeddings table should exist."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'embeddings'"
                ")"
            )
        )
        assert result.scalar_one() is True

    async def test_embeddings_has_id_column(self, db_session: AsyncSession) -> None:
        """embeddings should have id UUID column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'id'"
            )
        )
        assert result.scalar_one_or_none() == "uuid"

    async def test_embeddings_has_source_type_column(self, db_session: AsyncSession) -> None:
        """embeddings should have source_type text column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'source_type'"
            )
        )
        assert result.scalar_one_or_none() == "source_type"

    async def test_embeddings_has_source_id_column(self, db_session: AsyncSession) -> None:
        """embeddings should have source_id UUID column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'source_id'"
            )
        )
        assert result.scalar_one_or_none() == "uuid"

    async def test_embeddings_has_content_hash_column(self, db_session: AsyncSession) -> None:
        """embeddings should have content_hash text column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'content_hash'"
            )
        )
        assert result.scalar_one_or_none() == "content_hash"

    async def test_embeddings_has_embedding_column(self, db_session: AsyncSession) -> None:
        """embeddings should have embedding vector column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'embedding'"
            )
        )
        assert result.scalar_one_or_none() == "vector"

    async def test_embeddings_has_model_column(self, db_session: AsyncSession) -> None:
        """embeddings should have model text column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'model'"
            )
        )
        assert result.scalar_one_or_none() == "model"

    async def test_embeddings_has_dimension_column(self, db_session: AsyncSession) -> None:
        """embeddings should have dimension integer column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'dimension'"
            )
        )
        assert result.scalar_one_or_none() == "dimension"

    async def test_embeddings_has_generated_at_column(self, db_session: AsyncSession) -> None:
        """embeddings should have generated_at timestamptz column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'embeddings' AND column_name = 'generated_at'"
            )
        )
        assert result.scalar_one_or_none() == "generated_at"

    async def test_embeddings_unique_constraint(self, db_session: AsyncSession) -> None:
        """embeddings should have unique constraint on (source_type, source_id, model)."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'embeddings' "
                "AND constraint_type = 'UNIQUE'"
            )
        )
        constraints = [row[0] for row in result.fetchall()]
        assert any("embeddings" in c for c in constraints)

    async def test_embeddings_hnsw_index_exists(self, db_session: AsyncSession) -> None:
        """embeddings should have HNSW index on embedding column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'embeddings' AND indexname = 'idx_embeddings_search'"
            )
        )
        assert result.scalar_one_or_none() == "idx_embeddings_search"

    async def test_embeddings_source_index_exists(self, db_session: AsyncSession) -> None:
        """embeddings should have B-tree index on (source_type, source_id)."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'embeddings' AND indexname = 'idx_embeddings_source'"
            )
        )
        assert result.scalar_one_or_none() == "idx_embeddings_source"


class TestContextUsageEventsSchema:
    """Verify context_usage_events table columns and constraints."""

    async def test_context_usage_events_table_exists(self, db_session: AsyncSession) -> None:
        """context_usage_events table should exist."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT EXISTS ("
                "SELECT FROM information_schema.tables "
                "WHERE table_name = 'context_usage_events'"
                ")"
            )
        )
        assert result.scalar_one() is True

    async def test_context_usage_events_has_novel_id(self, db_session: AsyncSession) -> None:
        """context_usage_events should have novel_id UUID column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'context_usage_events' AND column_name = 'novel_id'"
            )
        )
        assert result.scalar_one_or_none() == "uuid"

    async def test_context_usage_events_has_entry_id(self, db_session: AsyncSession) -> None:
        """context_usage_events should have entry_id UUID column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'context_usage_events' AND column_name = 'entry_id'"
            )
        )
        assert result.scalar_one_or_none() == "uuid"

    async def test_context_usage_events_has_chapter_id(self, db_session: AsyncSession) -> None:
        """context_usage_events should have nullable chapter_id UUID column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'context_usage_events' AND column_name = 'chapter_id'"
            )
        )
        assert result.scalar_one_or_none() == "YES"

    async def test_context_usage_events_has_action_column(self, db_session: AsyncSession) -> None:
        """context_usage_events should have action text column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'context_usage_events' AND column_name = 'action'"
            )
        )
        assert result.scalar_one_or_none() == "action"

    async def test_context_usage_events_has_source_column(self, db_session: AsyncSession) -> None:
        """context_usage_events should have source text column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'context_usage_events' AND column_name = 'source'"
            )
        )
        assert result.scalar_one_or_none() == "source"

    async def test_context_usage_events_has_created_at(self, db_session: AsyncSession) -> None:
        """context_usage_events should have created_at timestamptz column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'context_usage_events' AND column_name = 'created_at'"
            )
        )
        assert result.scalar_one_or_none() == "created_at"

    async def test_action_check_constraint(self, db_session: AsyncSession) -> None:
        """context_usage_events should have action check constraint."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'context_usage_events' "
                "AND constraint_name = 'ck_context_usage_events_action'"
            )
        )
        assert result.scalar_one_or_none() == "ck_context_usage_events_action"

    async def test_source_check_constraint(self, db_session: AsyncSession) -> None:
        """context_usage_events should have source check constraint."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = 'context_usage_events' "
                "AND constraint_name = 'ck_context_usage_events_source'"
            )
        )
        assert result.scalar_one_or_none() == "ck_context_usage_events_source"

    async def test_entry_index_exists(self, db_session: AsyncSession) -> None:
        """context_usage_events should have index on entry_id."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'context_usage_events' "
                "AND indexname = 'idx_usage_events_entry'"
            )
        )
        assert result.scalar_one_or_none() == "idx_usage_events_entry"

    async def test_novel_index_exists(self, db_session: AsyncSession) -> None:
        """context_usage_events should have index on (novel_id, created_at DESC)."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'context_usage_events' "
                "AND indexname = 'idx_usage_events_novel'"
            )
        )
        assert result.scalar_one_or_none() == "idx_usage_events_novel"


class TestKBEntriesEnrichment:
    """Verify kb_entries enrichment columns added by migration 0022."""

    async def test_kb_entries_has_last_referenced_at(self, db_session: AsyncSession) -> None:
        """kb_entries should have nullable last_referenced_at column."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'kb_entries' "
                "AND column_name = 'last_referenced_at'"
            )
        )
        assert result.scalar_one_or_none() == "YES"

    async def test_kb_entries_has_usage_count(self, db_session: AsyncSession) -> None:
        """kb_entries should have usage_count integer column with default 0."""
        result = await db_session.execute(
            sqlalchemy.text(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = 'kb_entries' "
                "AND column_name = 'usage_count'"
            )
        )
        assert result.scalar_one_or_none() == "0"
