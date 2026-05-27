"""Unit tests for SceneService — scene-by-scene generation logic."""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.writing.scene_service import SceneService

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
        service = SceneService(repo=_FakeRepo())  # type: ignore[arg-type]
        request = _FakeRequestModel()
        result = await service.next_scene(request)  # type: ignore[arg-type]
        assert result.request_id == request.id
        assert result.scene_number == 1
        assert result.status == "streaming"


class TestAcceptScene:
    @pytest.mark.asyncio
    async def test_accept_scene_returns_accept_response(self) -> None:
        service = SceneService(repo=_FakeRepo())  # type: ignore[arg-type]
        request = _FakeRequestModel()
        result = await service.accept_scene(request, scene_number=1)  # type: ignore[arg-type]
        assert result.request_id == request.id
        assert result.chapter_id == request.chapter_id
        assert result.word_count == 150

    @pytest.mark.asyncio
    async def test_accept_scene_records_feedback_when_available(self) -> None:
        feedback = _FakeFeedbackCollector()
        service = SceneService(repo=_FakeRepo(), feedback_service=feedback)  # type: ignore[arg-type]
        request = _FakeRequestModel()
        await service.accept_scene(request, scene_number=1)  # type: ignore[arg-type]
        assert len(feedback.recorded) == 1

    @pytest.mark.asyncio
    async def test_accept_scene_no_feedback_when_none(self) -> None:
        service = SceneService(repo=_FakeRepo(), feedback_service=None)  # type: ignore[arg-type]
        request = _FakeRequestModel()
        result = await service.accept_scene(request, scene_number=1)  # type: ignore[arg-type]
        assert result.request_id == request.id
