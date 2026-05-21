"""Verify generation_requests table schema matches model.

These tests run against the real database to ensure migration
0008_generation_requests applies cleanly and the GenerationRequest
model maps correctly to the resulting table.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text

from narrare.writing.models import GenerationRequest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.requires_db


class TestGenerationRequestsTable:
    """Verify generation_requests columns exist after migration."""

    async def test_table_has_all_expected_columns(self, db_session: AsyncSession) -> None:
        """All GenerationRequest model columns must exist in the DB."""
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'generation_requests' "
                "ORDER BY column_name"
            )
        )
        columns = {row[0] for row in result}
        expected = {
            "id",
            "chapter_id",
            "status",
            "mode",
            "tone",
            "model_id",
            "provider_name",
            "tokens_used",
            "word_count",
            "started_at",
            "completed_at",
            "error_message",
            "user_id",
            "novel_id",
            "created_at",
            "updated_at",
        }
        assert expected.issubset(columns), f"Missing columns: {expected - columns}"

    async def test_chapter_versions_has_generation_request_id(
        self, db_session: AsyncSession
    ) -> None:
        """chapter_versions.generation_request_id column must exist."""
        result = await db_session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'chapter_versions' "
                "AND column_name = 'generation_request_id'"
            )
        )
        assert result.scalar_one_or_none() == "generation_request_id"

    async def test_create_and_query_generation_request(self, db_session: AsyncSession) -> None:
        """GenerationRequest model can be created and queried."""
        gen_id = uuid.uuid4()
        chapter_id = uuid.uuid4()
        user_id = uuid.uuid4()
        novel_id = uuid.uuid4()

        request = GenerationRequest(
            id=gen_id,
            chapter_id=chapter_id,
            user_id=user_id,
            novel_id=novel_id,
            mode="full_draft",
            status="pending",
            tone="dramatic",
        )
        db_session.add(request)
        await db_session.flush()

        result = await db_session.execute(
            select(GenerationRequest).where(GenerationRequest.id == gen_id)
        )
        found = result.scalar_one()
        assert found.mode == "full_draft"
        assert found.status == "pending"
        assert found.tone == "dramatic"
        assert found.tokens_used == 0
        assert found.word_count == 0
        assert found.error_message is None

    async def test_default_status_is_pending(self, db_session: AsyncSession) -> None:
        """Server default for status column is 'pending'."""
        gen_id = uuid.uuid4()
        request = GenerationRequest(
            id=gen_id,
            chapter_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            mode="scene_by_scene",
        )
        db_session.add(request)
        await db_session.flush()

        result = await db_session.execute(
            text("SELECT status FROM generation_requests WHERE id = :id").bindparams(id=gen_id)
        )
        db_status = result.scalar_one()
        assert db_status == "pending"

    async def test_status_update_via_model(self, db_session: AsyncSession) -> None:
        """Status can be updated from pending to streaming."""
        gen_id = uuid.uuid4()
        request = GenerationRequest(
            id=gen_id,
            chapter_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            novel_id=uuid.uuid4(),
            mode="full_draft",
        )
        db_session.add(request)
        await db_session.flush()

        request.status = "streaming"
        request.model_id = "claude-sonnet-4-5-20251020"
        request.provider_name = "anthropic"
        await db_session.flush()

        result = await db_session.execute(
            select(GenerationRequest).where(GenerationRequest.id == gen_id)
        )
        found = result.scalar_one()
        assert found.status == "streaming"
        assert found.model_id == "claude-sonnet-4-5-20251020"
        assert found.provider_name == "anthropic"
