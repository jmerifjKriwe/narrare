"""Unit tests for CoAuthorService.stream_coauthor — lifecycle and error handling.

Tests the ``stream_coauthor`` method of
:class:`CoAuthorService` without touching the database.
All dependencies are mocked (DI pattern, RULE-07).

Covers:
1. stream_coauthor: happy path — chunks streamed, draft processed, status transitions
2. stream_coauthor: pipeline error — marks failed, error message logged
3. stream_coauthor: intermediate chunks yielded in order
4. stream_coauthor: context markers included when context_before/after provided
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare.writing.coauthor_service import CoAuthorService
from narrare.writing.repository import GenerationRepository
from narrare.writing.schemas_coauthor import CoAuthorFocus, CoAuthorRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.memory.protocols import FeedbackCollector
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.pipeline import WritingPipeline
from tests.unit.api.writing._test_coauthor_helpers import _make_generation_request

if TYPE_CHECKING:
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USAGE = TokenUsage(prompt_tokens=20, completion_tokens=100, total_tokens=120)

CONFIG = ResolvedModelConfig(
    provider_name="test",
    model_id="test-model",
    temperature=0.7,
    max_tokens=4000,
)

_SELECTION = (
    "This is a sufficiently long selection text that demonstrates the "
    "co-author streaming flow. It needs to exceed fifty characters "
    "to satisfy Pydantic's min_length constraint on CoAuthorRequest."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request(**kw: Any) -> CoAuthorRequest:
    """Build a valid CoAuthorRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "selection_text": _SELECTION,
        "focus": [CoAuthorFocus.WORD_CHOICE],
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return CoAuthorRequest(**defaults)


async def _fake_stream(*chunks: StreamChunk) -> Any:
    """Async generator yielding StreamChunks — used as pipeline.generate return."""
    for c in chunks:
        yield c


# ---------------------------------------------------------------------------
# stream_coauthor: happy path
# ---------------------------------------------------------------------------


def _gate_open_repos() -> tuple[AsyncMock, AsyncMock]:
    """S6 gate-open repos (chapter binds to ANY novel, every novel owned)."""
    from tests.factories import make_chapter, make_novel

    chapter_repo = AsyncMock(spec=["get"])
    chapter_repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    novel_repo = AsyncMock(spec=["get_by_id"])
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return chapter_repo, novel_repo


class TestStreamCoauthorHappyPath:
    """Tests for successful stream_coauthor execution."""

    @pytest.mark.asyncio
    async def test_happy_path_creates_request_and_streams(self) -> None:
        """Successful stream: creates request, updates statuses, yields chunks."""
        request_id = uuid4()
        repo: AsyncMock = AsyncMock(spec=GenerationRepository)
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=request_id)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.update_status = AsyncMock()

        pipeline: MagicMock = MagicMock(spec=WritingPipeline)
        pipeline.generate = MagicMock(
            spec=[],  # type: ignore[method-assign]
            return_value=_fake_stream(
                StreamChunk(text="Revised "),
                StreamChunk(text="text."),
                StreamChunk(text="", is_final=True, usage=USAGE),
            ),
        )

        proc: MagicMock = MagicMock(spec=DraftProcessor)
        proc.process = MagicMock(
            spec=[],  # type: ignore[method-assign]
            side_effect=lambda text, **kw: text,
        )

        cr, nr = _gate_open_repos()
        service = CoAuthorService(
            repo=cast("GenerationRepository", repo),
            pipeline=cast("WritingPipeline", pipeline),
            draft_processor=cast("DraftProcessor", proc),
            config=CONFIG,
            chapter_repo=cast("ChapterRepository", cr),
            novel_repo=cast("NovelRepository", nr),
        )

        req = _request()
        chunks: list[StreamChunk] = []
        async for chunk in service.stream_coauthor(uuid4(), uuid4(), str(uuid4()), req):
            chunks.append(chunk)

        # All chunks yielded in order
        assert len(chunks) == 3
        assert chunks[0].text == "Revised "
        assert chunks[1].text == "text."
        assert chunks[2].is_final
        assert chunks[2].usage == USAGE

        # Repository interactions
        repo.create.assert_called_once()
        assert repo.update_status.call_count == 2

        # Status transitions: streaming → completed
        first_call = repo.update_status.call_args_list[0]
        assert first_call[0][1] == "streaming"

        second_call = repo.update_status.call_args_list[1]
        assert second_call[0][1] == "completed"

    @pytest.mark.asyncio
    async def test_intermediate_chunks_yielded_before_final(self) -> None:
        """Multiple intermediate chunks are yielded before the final chunk."""
        request_id = uuid4()
        repo: AsyncMock = AsyncMock(spec=GenerationRepository)
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=request_id)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.update_status = AsyncMock()

        pipeline: MagicMock = MagicMock(spec=WritingPipeline)
        pipeline.generate = MagicMock(
            spec=[],  # type: ignore[method-assign]
            return_value=_fake_stream(
                StreamChunk(text="Part 1. "),
                StreamChunk(text="Part 2. "),
                StreamChunk(text="Part 3."),
                StreamChunk(text="", is_final=True, usage=USAGE),
            ),
        )

        proc: MagicMock = MagicMock(spec=DraftProcessor)
        proc.process = MagicMock(
            spec=[],  # type: ignore[method-assign]
            side_effect=lambda text, **kw: text,
        )

        cr, nr = _gate_open_repos()
        service = CoAuthorService(
            repo=cast("GenerationRepository", repo),
            pipeline=cast("WritingPipeline", pipeline),
            draft_processor=cast("DraftProcessor", proc),
            config=CONFIG,
            chapter_repo=cast("ChapterRepository", cr),
            novel_repo=cast("NovelRepository", nr),
        )

        req = _request()
        texts: list[str] = []
        async for chunk in service.stream_coauthor(uuid4(), uuid4(), str(uuid4()), req):
            texts.append(chunk.text)

        assert texts == ["Part 1. ", "Part 2. ", "Part 3.", ""]

    @pytest.mark.asyncio
    async def test_final_chunk_context_meta_injects_request_id(self) -> None:
        """Final chunk with context_meta gets request_id injected."""
        request_id = uuid4()
        repo: AsyncMock = AsyncMock(spec=GenerationRepository)
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=request_id)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.update_status = AsyncMock()

        pipeline: MagicMock = MagicMock(spec=WritingPipeline)
        pipeline.generate = MagicMock(
            spec=[],  # type: ignore[method-assign]
            return_value=_fake_stream(
                StreamChunk(
                    text="",
                    is_final=True,
                    usage=USAGE,
                    context_meta={
                        "changes": [],
                        "total_changes": 0,
                        "has_changes": False,
                    },
                ),
            ),
        )

        proc: MagicMock = MagicMock(spec=DraftProcessor)
        proc.process = MagicMock(
            spec=[],  # type: ignore[method-assign]
            side_effect=lambda text, **kw: text,
        )

        cr, nr = _gate_open_repos()
        service = CoAuthorService(
            repo=cast("GenerationRepository", repo),
            pipeline=cast("WritingPipeline", pipeline),
            draft_processor=cast("DraftProcessor", proc),
            config=CONFIG,
            chapter_repo=cast("ChapterRepository", cr),
            novel_repo=cast("NovelRepository", nr),
        )

        req = _request()
        chunks: list[StreamChunk] = []
        async for chunk in service.stream_coauthor(uuid4(), uuid4(), str(uuid4()), req):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].is_final
        assert chunks[0].context_meta is not None
        assert chunks[0].context_meta.get("request_id") == str(request_id)

    @pytest.mark.asyncio
    async def test_successful_stream_records_feedback(self) -> None:
        """Successful stream records feedback via feedback service."""
        request_id = uuid4()
        gen_request = _make_generation_request(id=request_id)

        repo: AsyncMock = AsyncMock(spec=GenerationRepository)
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=request_id)
        repo.get_by_id = AsyncMock(return_value=gen_request)
        repo.update_status = AsyncMock()

        pipeline: MagicMock = MagicMock(spec=WritingPipeline)
        pipeline.generate = MagicMock(
            spec=[],  # type: ignore[method-assign]
            return_value=_fake_stream(
                StreamChunk(text="Revised text."),
                StreamChunk(text="", is_final=True, usage=USAGE),
            ),
        )

        proc: MagicMock = MagicMock(spec=DraftProcessor)
        proc.process = MagicMock(
            spec=[],  # type: ignore[method-assign]
            side_effect=lambda text, **kw: text,
        )

        feedback_service: AsyncMock = AsyncMock(spec=FeedbackCollector)

        cr, nr = _gate_open_repos()
        service = CoAuthorService(
            repo=cast("GenerationRepository", repo),
            pipeline=cast("WritingPipeline", pipeline),
            draft_processor=cast("DraftProcessor", proc),
            config=CONFIG,
            chapter_repo=cast("ChapterRepository", cr),
            novel_repo=cast("NovelRepository", nr),
            feedback_service=cast("FeedbackCollector", feedback_service),
        )

        req = _request()
        chunks: list[StreamChunk] = []
        async for chunk in service.stream_coauthor(uuid4(), uuid4(), str(uuid4()), req):
            chunks.append(chunk)

        assert len(chunks) == 2
        repo.get_by_id.assert_called_once_with(request_id)
        feedback_service.record.assert_called_once()


# ---------------------------------------------------------------------------
# stream_coauthor: pipeline error handling
# ---------------------------------------------------------------------------


class TestStreamCoauthorErrors:
    """Tests for stream_coauthor error handling."""

    @pytest.mark.asyncio
    async def test_pipeline_error_marks_failed(self) -> None:
        """Pipeline error updates status to failed with error message."""
        request_id = uuid4()
        repo: AsyncMock = AsyncMock(spec=GenerationRepository)
        repo.get_active_for_chapter = AsyncMock(return_value=None)
        repo.create = AsyncMock(return_value=request_id)
        repo.update_status = AsyncMock()

        pipeline: MagicMock = MagicMock(spec=WritingPipeline)
        pipeline.generate = MagicMock(
            spec=[],  # type: ignore[method-assign]
            side_effect=ValueError("LLM connection failed"),
        )

        proc: MagicMock = MagicMock(spec=DraftProcessor)
        proc.process = MagicMock(
            spec=[],  # type: ignore[method-assign]
            side_effect=lambda text, **kw: text,
        )

        cr, nr = _gate_open_repos()
        service = CoAuthorService(
            repo=cast("GenerationRepository", repo),
            pipeline=cast("WritingPipeline", pipeline),
            draft_processor=cast("DraftProcessor", proc),
            config=CONFIG,
            chapter_repo=cast("ChapterRepository", cr),
            novel_repo=cast("NovelRepository", nr),
        )

        req = _request()
        chunks: list[StreamChunk] = []
        async for chunk in service.stream_coauthor(uuid4(), uuid4(), str(uuid4()), req):
            chunks.append(chunk)

        # No chunks yielded (error before any yield from pipeline)
        assert len(chunks) == 0

        # Status should be updated to failed (after streaming)
        assert repo.update_status.call_count >= 2
        last_call = repo.update_status.call_args_list[-1]
        assert last_call[0][1] == "failed"
        assert "error_message" in last_call.kwargs
        assert "LLM connection failed" in last_call.kwargs["error_message"]
