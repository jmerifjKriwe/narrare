"""Unit tests for WritingService — accept, reject, stop, scenes, stats, ownership.

Split from test_writing_service.py for RULE-04 compliance.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.models import GenerationRequest
from narrare.writing.service import WritingService
from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.shared.errors import NotFoundError


def _make_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.7,
        max_tokens=4000,
    )


def _make_db_request(
    *,
    status: str = "pending",
    mode: str = "full_draft",
    word_count: int = 0,
    user_id: uuid.UUID | None = None,
) -> GenerationRequest:
    uid = user_id or uuid.uuid4()
    request = GenerationRequest(
        id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        novel_id=uuid.uuid4(),
        user_id=uid,
        mode=mode,
        status=status,
        word_count=word_count,
    )
    return request


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=uuid.uuid4())
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_active_for_chapter = AsyncMock(return_value=None)
    repo.update_status = AsyncMock()
    repo.get_stats_for_novel = AsyncMock(
        return_value={
            "total_generations": 5,
            "success_rate": 0.8,
            "avg_tokens": 1500.0,
            "avg_word_count": 2000.0,
            "most_used_model": "claude-sonnet-4-5-20251020",
        }
    )
    return repo


@pytest.fixture
def mock_pipeline() -> AsyncMock:
    pipeline = AsyncMock()
    pipeline.stop = AsyncMock()
    return pipeline


@pytest.fixture
def mock_draft_processor() -> MagicMock:
    processor = MagicMock(spec=["process"])
    processor.process = MagicMock(spec=[], side_effect=lambda text, **kwargs: text)
    return processor


@pytest.fixture
def config() -> ResolvedModelConfig:
    return _make_config()


@pytest.fixture
def service(
    mock_repo: AsyncMock,
    mock_pipeline: AsyncMock,
    mock_draft_processor: MagicMock,
    config: ResolvedModelConfig,
) -> WritingService:
    return WritingService(
        repo=mock_repo,
        pipeline=mock_pipeline,
        draft_processor=mock_draft_processor,
        config=config,
    )


class TestAcceptDraft:
    async def test_accept_draft_returns_accept_response(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """accept_draft() returns AcceptResponse with correct fields."""
        uid = uuid.uuid4()
        db_request = _make_db_request(user_id=uid, word_count=1500)
        mock_repo.get_by_id.return_value = db_request

        response = await service.accept_draft(
            db_request.id,
            str(uid),
        )

        assert response.request_id == db_request.id
        assert response.chapter_id == db_request.chapter_id
        assert response.word_count == 1500

    async def test_accept_draft_with_modified_text(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """accept_draft() accepts optional modified_text."""
        uid = uuid.uuid4()
        db_request = _make_db_request(user_id=uid)
        mock_repo.get_by_id.return_value = db_request

        response = await service.accept_draft(
            db_request.id,
            str(uid),
            modified_text="Edited version",
        )
        assert response.request_id == db_request.id


class TestRejectDraft:
    async def test_reject_draft_returns_reject_response(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """reject_draft() returns RejectResponse with rejected status."""
        uid = uuid.uuid4()
        db_request = _make_db_request(user_id=uid)
        mock_repo.get_by_id.return_value = db_request

        response = await service.reject_draft(db_request.id, str(uid))

        assert response.request_id == db_request.id
        assert response.status == "rejected"


class TestStopGeneration:
    async def test_stop_generation_calls_pipeline_stop(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
        mock_pipeline: AsyncMock,
    ) -> None:
        """stop_generation() signals pipeline and updates status."""
        uid = uuid.uuid4()
        db_request = _make_db_request(
            user_id=uid,
            status="streaming",
            word_count=500,
        )
        mock_repo.get_by_id.return_value = db_request

        response = await service.stop_generation(db_request.id, str(uid))

        assert response.status == "stopped"
        assert response.word_count == 500
        mock_pipeline.stop.assert_called_once_with(db_request.id)
        mock_repo.update_status.assert_called_once()


class TestGetStats:
    async def test_get_stats_returns_aggregated_stats(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """get_stats() returns GenerationStatsResponse from repo data."""
        response = await service.get_stats(uuid.uuid4(), str(uuid.uuid4()))

        assert response.total_generations == 5
        assert response.success_rate == 0.8
        assert response.avg_tokens == 1500.0
        assert response.avg_word_count == 2000.0
        assert response.most_used_model == "claude-sonnet-4-5-20251020"


class TestOwnership:
    async def test_get_nonexistent_request_raises_not_found(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """Operations on non-existent request raise NotFoundError."""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.accept_draft(uuid.uuid4(), str(uuid.uuid4()))

    async def test_wrong_owner_raises_not_found(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """Requests belonging to another user raise NotFoundError."""
        uid = uuid.uuid4()
        other_uid = uuid.uuid4()
        db_request = _make_db_request(user_id=uid)
        mock_repo.get_by_id.return_value = db_request

        with pytest.raises(NotFoundError):
            await service.accept_draft(db_request.id, str(other_uid))


class TestSceneOperations:
    async def test_next_scene_returns_scene_response(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """next_scene() returns SceneNextResponse."""
        uid = uuid.uuid4()
        db_request = _make_db_request(user_id=uid, mode="scene_by_scene")
        mock_repo.get_by_id.return_value = db_request

        response = await service.next_scene(db_request.id, str(uid))

        assert response.request_id == db_request.id
        assert response.scene_number == 1

    async def test_accept_scene_returns_accept_response(
        self,
        service: WritingService,
        mock_repo: AsyncMock,
    ) -> None:
        """accept_scene() returns AcceptResponse."""
        uid = uuid.uuid4()
        db_request = _make_db_request(user_id=uid, mode="scene_by_scene")
        mock_repo.get_by_id.return_value = db_request

        response = await service.accept_scene(
            db_request.id,
            1,
            str(uid),
        )

        assert response.request_id == db_request.id
        assert response.chapter_id == db_request.chapter_id
