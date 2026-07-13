"""Unit tests for WritingService session-memory wiring (ADR-045 Decision 8).

Tests verify that cross-session writing context is fetched from mem0
before generation and recorded after completion.  Graceful degradation
(RULE-11): when ``session_memory`` is ``None``, no fetch/record occurs
and existing behaviour is unchanged.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare.writing.service import WritingService
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.memory.protocols import SessionMemoryCollector
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.pipeline import WritingPipeline

if TYPE_CHECKING:
    from narrare_core.llm import ResolvedModelConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request_model(user_id: uuid.UUID) -> SimpleNamespace:
    """Create a fake GenerationRequest ORM model with valid attributes."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        novel_id=uuid.uuid4(),
        user_id=user_id,
        mode="full_draft",
        tone="balanced",
        status="pending",
        word_count=0,
    )


def _make_streaming_pipeline(
    *,
    capture: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock WritingPipeline whose generate() yields text + final chunk.

    Args:
        capture: Optional dict to record kwargs passed to ``generate()``.
    """
    pipeline = MagicMock(spec=WritingPipeline)
    pipeline.stop = AsyncMock()

    async def _generate(*_args: Any, **kwargs: Any) -> Any:
        if capture is not None:
            capture.update(kwargs)
        yield StreamChunk(text="Hello ")
        yield StreamChunk(
            text="world.",
            is_final=True,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

    pipeline.generate = _generate
    return pipeline


def _make_draft_processor() -> MagicMock:
    """Mock DraftProcessor — returns input text unchanged."""
    processor = MagicMock(spec=DraftProcessor)
    processor.process.side_effect = lambda text, **_kw: text
    return processor


@pytest.fixture
def mock_session_memory() -> AsyncMock:
    """Mock SessionMemoryCollector protocol."""
    memory = AsyncMock(spec=SessionMemoryCollector)
    memory.get_cross_session_context.return_value = "- Past session note"
    return memory


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestWritingServiceSessionMemoryConstructor:
    def test_writing_service_accepts_and_stores_session_memory(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """WritingService constructor stores session_memory when provided."""
        memory = AsyncMock(spec=SessionMemoryCollector)
        service = WritingService(
            repo=mock_repo,
            pipeline=MagicMock(spec=WritingPipeline),
            draft_processor=MagicMock(spec=DraftProcessor),
            config=config,
            session_memory=memory,
        )
        assert service._session_memory is memory

    def test_writing_service_defaults_session_memory_to_none(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """WritingService defaults session_memory to None when not provided."""
        service = WritingService(
            repo=mock_repo,
            pipeline=MagicMock(spec=WritingPipeline),
            draft_processor=MagicMock(spec=DraftProcessor),
            config=config,
        )
        assert service._session_memory is None


# ---------------------------------------------------------------------------
# stream_generation — session memory wiring
# ---------------------------------------------------------------------------


class TestStreamGenerationSessionMemory:
    """Tests for cross-session context fetch and session recording."""

    async def test_fetches_cross_session_context_when_session_memory_provided(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
        mock_session_memory: AsyncMock,
    ) -> None:
        """stream_generation() fetches context and passes result to pipeline."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        capture: dict[str, Any] = {}
        pipeline = _make_streaming_pipeline(capture=capture)

        service = WritingService(
            repo=mock_repo,
            pipeline=pipeline,
            draft_processor=_make_draft_processor(),
            config=config,
            session_memory=mock_session_memory,
        )

        # Consume the entire stream
        _chunks = [
            chunk
            async for chunk in service.stream_generation(
                request_model.id,
                str(user_id),
            )
        ]

        # Context was fetched with correct user + novel IDs
        mock_session_memory.get_cross_session_context.assert_called_once_with(
            user_id,
            request_model.novel_id,
        )
        # Fetched context was forwarded to the pipeline
        assert capture["cross_session_context"] == "- Past session note"

    async def test_records_session_after_completion_when_session_memory_provided(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
        mock_session_memory: AsyncMock,
    ) -> None:
        """stream_generation() records the writing session after final chunk."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        pipeline = _make_streaming_pipeline()

        service = WritingService(
            repo=mock_repo,
            pipeline=pipeline,
            draft_processor=_make_draft_processor(),
            config=config,
            session_memory=mock_session_memory,
        )

        _chunks = [
            chunk
            async for chunk in service.stream_generation(
                request_model.id,
                str(user_id),
            )
        ]

        mock_session_memory.record_writing_session.assert_called_once_with(
            user_id,
            request_model.novel_id,
            mode="full_draft",
            chapter_title=str(request_model.chapter_id),
            word_count=2,
        )

    async def test_works_without_session_memory_backward_compatible(
        self,
        mock_repo: AsyncMock,
        config: ResolvedModelConfig,
    ) -> None:
        """stream_generation() with session_memory=None fetches/records nothing."""
        user_id = uuid.uuid4()
        request_model = _make_request_model(user_id)
        mock_repo.get_by_id.return_value = request_model

        capture: dict[str, Any] = {}
        pipeline = _make_streaming_pipeline(capture=capture)

        service = WritingService(
            repo=mock_repo,
            pipeline=pipeline,
            draft_processor=_make_draft_processor(),
            config=config,
            # session_memory not provided — defaults to None
        )

        chunks = [
            chunk
            async for chunk in service.stream_generation(
                request_model.id,
                str(user_id),
            )
        ]

        # Stream still produces all chunks (backward compat)
        assert len(chunks) == 2
        assert chunks[-1].is_final is True
        # Empty cross-session context passed to pipeline
        assert capture.get("cross_session_context") == ""
