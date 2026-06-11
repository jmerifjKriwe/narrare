"""Unit tests for SceneService — scene-by-scene generation logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.writing.scene_service import SceneService

if TYPE_CHECKING:
    from narrare.writing.models import GenerationRequest
    from narrare.writing.repository import GenerationRepository
    from narrare_core.memory.protocols import FeedbackCollector

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRequestModel:
    def __init__(self) -> None:
        self.id = uuid4()
        self.chapter_id = uuid4()
        self.novel_id = uuid4()
        self.user_id = uuid4()
        self.status = "streaming"
        self.word_count = 150


class _FakeFeedbackCollector:
    def __init__(self) -> None:
        self.recorded: list[object] = []

    async def record(self, event: object) -> None:
        self.recorded.append(event)


class _FakeRepo:
    pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNextScene:
    @pytest.mark.asyncio
    async def test_next_scene_returns_current_state(self) -> None:
        service = SceneService(repo=cast("GenerationRepository", _FakeRepo()))
        request = _FakeRequestModel()
        result = await service.next_scene(cast("GenerationRequest", request))
        assert result.request_id == request.id
        assert result.scene_number == 1
        assert result.status == "streaming"


class TestAcceptScene:
    @pytest.mark.asyncio
    async def test_accept_scene_returns_accept_response(self) -> None:
        service = SceneService(repo=cast("GenerationRepository", _FakeRepo()))
        request = _FakeRequestModel()
        result = await service.accept_scene(cast("GenerationRequest", request), scene_number=1)
        assert result.request_id == request.id
        assert result.chapter_id == request.chapter_id
        assert result.word_count == 150

    @pytest.mark.asyncio
    async def test_accept_scene_records_feedback_when_available(self) -> None:
        feedback = _FakeFeedbackCollector()
        service = SceneService(
            repo=cast("GenerationRepository", _FakeRepo()),
            feedback_service=cast("FeedbackCollector", feedback),
        )
        request = _FakeRequestModel()
        await service.accept_scene(cast("GenerationRequest", request), scene_number=1)
        assert len(feedback.recorded) == 1

    @pytest.mark.asyncio
    async def test_accept_scene_no_feedback_when_none(self) -> None:
        service = SceneService(
            repo=cast("GenerationRepository", _FakeRepo()), feedback_service=None
        )
        request = _FakeRequestModel()
        result = await service.accept_scene(cast("GenerationRequest", request), scene_number=1)
        assert result.request_id == request.id
