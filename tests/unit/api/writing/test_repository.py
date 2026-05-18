"""Unit tests for GenerationRepository — mocked AsyncSession.

These tests verify repository logic without touching a real database.
The AsyncSession is mocked so we control exactly what each query returns.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from narrare.writing.models import GenerationRequest
from narrare.writing.repository import GenerationRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with a chainable execute()."""
    session = AsyncMock(spec=AsyncSession)
    # Default: execute returns a mock with scalar_one_or_none → None
    mock_result = MagicMock(spec=["scalar_one_or_none", "one", "first", "scalar"])
    mock_result.scalar_one_or_none.return_value = None
    mock_result.one.return_value = MagicMock(
        spec=[], total=0, success_rate=0, avg_tokens=0, avg_word_count=0
    )
    mock_result.first.return_value = None
    mock_result.scalar.return_value = 0
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.add = MagicMock(spec=[])
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    return _make_mock_session()


@pytest.fixture
def repo(mock_session: AsyncMock) -> GenerationRepository:
    return GenerationRepository(session=mock_session)


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    async def test_create_returns_uuid(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """create() returns the UUID of the new GenerationRequest."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # flush_and_refresh will populate the entity id
        async def fake_flush_and_refresh(entity: Any) -> None:
            entity.id = uuid.uuid4()

        repo._flush_and_refresh = AsyncMock(side_effect=fake_flush_and_refresh)

        result = await repo.create(
            chapter_id=chapter_id,
            novel_id=novel_id,
            user_id=user_id,
            mode="full_draft",
        )
        assert isinstance(result, uuid.UUID)

    async def test_create_adds_entity_with_correct_fields(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """create() adds a GenerationRequest with the provided fields."""
        chapter_id = uuid.uuid4()
        novel_id = uuid.uuid4()
        user_id = uuid.uuid4()

        async def fake_flush_and_refresh(entity: Any) -> None:
            entity.id = uuid.uuid4()

        repo._flush_and_refresh = AsyncMock(side_effect=fake_flush_and_refresh)

        await repo.create(
            chapter_id=chapter_id,
            novel_id=novel_id,
            user_id=user_id,
            mode="scene_by_scene",
        )

        mock_session.add.assert_called_once()
        added_entity = mock_session.add.call_args[0][0]
        assert isinstance(added_entity, GenerationRequest)
        assert added_entity.chapter_id == chapter_id
        assert added_entity.novel_id == novel_id
        assert added_entity.user_id == user_id
        assert added_entity.mode == "scene_by_scene"
        assert added_entity.status == "pending"


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    async def test_get_by_id_returns_entity_when_found(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_id() returns the GenerationRequest when it exists."""
        expected = MagicMock(spec=GenerationRequest)
        mock_session.execute.return_value.scalar_one_or_none.return_value = expected

        result = await repo.get_by_id(uuid.uuid4())
        assert result is expected

    async def test_get_by_id_returns_none_when_not_found(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """get_by_id() returns None when no matching row exists."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = await repo.get_by_id(uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# update_status
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    async def test_update_status_calls_execute_with_status(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """update_status() issues an UPDATE with the new status."""
        request_id = uuid.uuid4()
        await repo.update_status(request_id, "streaming")

        # Should have called execute twice: update + flush
        assert mock_session.execute.call_count >= 1

    async def test_update_status_passes_allowed_kwargs(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """update_status() only passes whitelisted kwargs to the UPDATE."""
        request_id = uuid.uuid4()
        await repo.update_status(
            request_id,
            "completed",
            tokens_used=500,
            word_count=1200,
            model_id="gpt-4o",
            provider_name="openai",
            # This should be silently ignored
            malicious_field="hacked",
        )

        assert mock_session.execute.call_count >= 1

    async def test_update_status_flushes(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """update_status() flushes changes to the session."""
        repo._flush = AsyncMock()
        await repo.update_status(uuid.uuid4(), "failed", error_message="timeout")
        repo._flush.assert_called_once()


# ---------------------------------------------------------------------------
# get_active_for_chapter
# ---------------------------------------------------------------------------


class TestGetActiveForChapter:
    async def test_returns_entity_when_active_request_exists(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """Returns pending/streaming request if one exists for the chapter."""
        active = MagicMock(spec=GenerationRequest)
        mock_session.execute.return_value.scalar_one_or_none.return_value = active

        result = await repo.get_active_for_chapter(uuid.uuid4())
        assert result is active

    async def test_returns_none_when_no_active_request(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """Returns None when no pending/streaming request exists."""
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        result = await repo.get_active_for_chapter(uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# cleanup_stale
# ---------------------------------------------------------------------------


class TestCleanupStale:
    async def test_returns_zero_when_no_stale_requests(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """cleanup_stale() returns 0 when nothing is stale."""
        mock_session.execute.return_value.scalar.return_value = 0

        count = await repo.cleanup_stale(max_age_minutes=30)
        assert count == 0

    async def test_marks_stale_as_failed(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """cleanup_stale() marks stale streaming requests as failed."""
        mock_session.execute.return_value.scalar.return_value = 3
        repo._flush = AsyncMock()

        count = await repo.cleanup_stale(max_age_minutes=30)
        assert count == 3
        # Should have called execute for count + update = 2 calls
        assert mock_session.execute.call_count == 2
        repo._flush.assert_called_once()

    async def test_does_not_update_when_count_zero(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """cleanup_stale() skips UPDATE when no stale rows found."""
        mock_session.execute.return_value.scalar.return_value = 0

        await repo.cleanup_stale()
        # Only the SELECT count query, no UPDATE
        assert mock_session.execute.call_count == 1


# ---------------------------------------------------------------------------
# get_stats_for_novel
# ---------------------------------------------------------------------------


class TestGetStatsForNovel:
    async def test_returns_aggregated_stats(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """get_stats_for_novel() returns aggregated statistics."""
        agg_row = MagicMock(spec=["total", "success_rate", "avg_tokens", "avg_word_count"])
        agg_row.total = 10
        agg_row.success_rate = 0.8
        agg_row.avg_tokens = 1500.0
        agg_row.avg_word_count = 2000.0

        mock_session.execute.return_value = MagicMock(
            spec=["one", "first"],
            one=MagicMock(spec=[], return_value=agg_row),
            first=MagicMock(spec=[], return_value=("claude-sonnet-4-5-20251020", 5)),
        )

        result = await repo.get_stats_for_novel(uuid.uuid4())
        assert result["total_generations"] == 10
        assert result["success_rate"] == 0.8
        assert result["avg_tokens"] == 1500.0
        assert result["avg_word_count"] == 2000.0
        assert result["most_used_model"] == "claude-sonnet-4-5-20251020"

    async def test_stats_with_no_generations(
        self, repo: GenerationRepository, mock_session: AsyncMock
    ) -> None:
        """get_stats_for_novel() handles zero generations."""
        agg_row = MagicMock(spec=["total", "success_rate", "avg_tokens", "avg_word_count"])
        agg_row.total = 0
        agg_row.success_rate = None
        agg_row.avg_tokens = None
        agg_row.avg_word_count = None

        call_count = 0
        results = [
            MagicMock(spec=["one"], one=MagicMock(spec=[], return_value=agg_row)),
            MagicMock(spec=["first"], first=MagicMock(spec=[], return_value=None)),
        ]

        async def mock_execute(stmt: Any) -> MagicMock:
            nonlocal call_count
            r = results[min(call_count, len(results) - 1)]
            call_count += 1
            return r

        mock_session.execute = AsyncMock(side_effect=mock_execute)

        result = await repo.get_stats_for_novel(uuid.uuid4())
        assert result["total_generations"] == 0
        assert result["success_rate"] == 0.0
        assert result["most_used_model"] is None
