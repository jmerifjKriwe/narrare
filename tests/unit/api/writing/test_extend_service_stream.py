"""Unit tests for ExtendService — stream_extend lifecycle and error handling.

Split from test_extend_service.py per RULE-04.

Covers:
1. stream_extend: happy path — chunks streamed, draft processed, status transitions
2. stream_extend: LLM failure → marks failed, logs error
3. stream_extend: chapter_content construction (marker, text_after)
4. stream_extend: word target passed to pipeline request
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from narrare.writing.extend_service import ExtendService
from narrare.writing.schemas import ExtendLength, ExtendRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from tests.unit.api.writing._extend_factories import make_static_runtime_factory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USAGE = TokenUsage(prompt_tokens=20, completion_tokens=100, total_tokens=120)

CONFIG = ResolvedModelConfig(
    provider_name="test",
    model_id="test-model",
    temperature=0.7,
    max_tokens=4000,
)


def _request(**kw: Any) -> ExtendRequest:
    defaults: dict[str, Any] = {
        "text_before": "Alice walked through the dark forest. The trees loomed.",
        "length": ExtendLength.MEDIUM,
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return ExtendRequest(**defaults)


async def _fake_stream(*texts: str) -> Any:
    """Async generator yielding StreamChunks — used as pipeline.generate return."""
    for t in texts:
        yield StreamChunk(text=t)
    yield StreamChunk(text="", is_final=True, usage=USAGE)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_active_for_chapter = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=uuid.uuid4())
    repo.create_if_no_active = AsyncMock(return_value=uuid.uuid4())
    repo.update_status = AsyncMock()
    return repo


@pytest.fixture()
def mock_pipeline() -> MagicMock:
    """Pipeline mock — MagicMock so generate() returns async generator directly.

    The service iterates directly: ``async for chunk in pipeline.generate(...)``.
    AsyncMock would wrap the return value as a coroutine, breaking iteration.
    """
    pipeline = MagicMock(spec=["generate"])
    pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Default."))
    return pipeline


@pytest.fixture()
def mock_draft_processor() -> MagicMock:
    proc = MagicMock(spec=["process"])
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return proc


@pytest.fixture()
def service(
    mock_repo: AsyncMock,
    mock_pipeline: MagicMock,
    mock_draft_processor: MagicMock,
) -> ExtendService:
    from tests.factories import make_chapter, make_novel

    # S6 gate-open repos (chapter binds to ANY novel, every novel owned):
    # these tests exercise streaming behavior, not ownership — the access
    # matrix lives in test_generation_access_matrix.py.
    chapter_repo = AsyncMock(spec=["get"])
    chapter_repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    novel_repo = AsyncMock(spec=["get_by_id"])
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return ExtendService(
        repo=mock_repo,
        # ADR-086 L32: the service composes its runtime at first use; the
        # test chain pins a fixed runtime (render- and outcome-inert —
        # same config/pipeline the eager factory passed).
        runtime_factory=make_static_runtime_factory(mock_pipeline, CONFIG),
        draft_processor=mock_draft_processor,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )


# ---------------------------------------------------------------------------
# stream_extend: happy path
# ---------------------------------------------------------------------------


class TestStreamExtendHappyPath:
    async def test_streams_text_chunks(
        self, service: ExtendService, mock_pipeline: MagicMock
    ) -> None:
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("First. ", "Second."))

        chunks: list[StreamChunk] = []
        async for chunk in service.stream_extend(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            chunks.append(chunk)

        assert len(chunks) >= 2
        text_chunks = [c for c in chunks if c.text and not c.is_final]
        assert any("First" in c.text for c in text_chunks)

    async def test_final_chunk_has_usage(
        self, service: ExtendService, mock_pipeline: MagicMock
    ) -> None:
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Text."))

        chunks: list[StreamChunk] = []
        async for chunk in service.stream_extend(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            chunks.append(chunk)

        final = [c for c in chunks if c.is_final]
        assert len(final) == 1
        assert final[0].usage is not None

    async def test_status_transitions(
        self,
        service: ExtendService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Generated text."))

        async for _ in service.stream_extend(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        assert mock_repo.update_status.call_count == 2
        statuses = [c.args[1] for c in mock_repo.update_status.call_args_list]
        assert "streaming" in statuses
        assert "completed" in statuses

    async def test_draft_processor_applied_on_final(
        self,
        service: ExtendService,
        mock_pipeline: MagicMock,
        mock_draft_processor: MagicMock,
    ) -> None:
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Raw text."))

        async for _ in service.stream_extend(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        mock_draft_processor.process.assert_called()


# ---------------------------------------------------------------------------
# stream_extend: LLM failure
# ---------------------------------------------------------------------------


class TestStreamExtendLLMFailure:
    async def test_marks_failed_on_exception(
        self,
        service: ExtendService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        async def _failing_gen() -> Any:
            yield StreamChunk(text="Partial ")
            raise RuntimeError("LLM connection lost")

        mock_pipeline.generate = MagicMock(spec=[], return_value=_failing_gen())

        chunks: list[StreamChunk] = []
        async for chunk in service.stream_extend(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            chunks.append(chunk)

        assert any("Partial" in c.text for c in chunks)
        statuses = [c.args[1] for c in mock_repo.update_status.call_args_list]
        assert "failed" in statuses

    async def test_error_message_recorded(
        self,
        service: ExtendService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        async def _failing_gen() -> Any:
            if False:
                yield  # makes this an async generator
            raise RuntimeError("Model overloaded")

        mock_pipeline.generate = MagicMock(spec=[], return_value=_failing_gen())

        async for _ in service.stream_extend(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        failed_calls = [c for c in mock_repo.update_status.call_args_list if c.args[1] == "failed"]
        assert len(failed_calls) == 1
        assert "Model overloaded" in str(failed_calls[0])


# ---------------------------------------------------------------------------
# stream_extend: chapter_content construction
# ---------------------------------------------------------------------------


class TestChapterContentConstruction:
    async def test_marker_without_text_after(
        self,
        service: ExtendService,
        mock_pipeline: MagicMock,
    ) -> None:
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("x"))

        req = _request(text_after=None)
        async for _ in service.stream_extend(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        cc = mock_pipeline.generate.call_args.kwargs.get("chapter_content", "")
        assert "[CONTINUE FROM HERE]" in cc
        assert req.text_before in cc
        assert cc.endswith("\n")

    async def test_marker_with_text_after(
        self,
        service: ExtendService,
        mock_pipeline: MagicMock,
    ) -> None:
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Continued."))

        req = _request(text_after="The sun was setting.")
        async for _ in service.stream_extend(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        cc = mock_pipeline.generate.call_args.kwargs.get("chapter_content", "")
        assert req.text_before in cc
        assert "[CONTINUE FROM HERE]" in cc
        assert "The sun was setting." in cc


# ---------------------------------------------------------------------------
# stream_extend: word target passed to pipeline
# ---------------------------------------------------------------------------


class TestWordTargetPassedToPipeline:
    @pytest.mark.parametrize(
        "length,expected",
        [
            (ExtendLength.SHORT, 150),
            (ExtendLength.MEDIUM, 400),
            (ExtendLength.LONG, 750),
        ],
    )
    async def test_word_target_by_length(
        self,
        service: ExtendService,
        mock_pipeline: MagicMock,
        length: ExtendLength,
        expected: int,
    ) -> None:
        from narrare_core.writing._enums import GenerationMode
        from narrare_core.writing.models import (
            GenerationRequest as CoreReq,
        )

        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Text."))

        req = _request(length=length)
        async for _ in service.stream_extend(uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), req):
            pass

        pipeline_req = mock_pipeline.generate.call_args.args[0]
        assert isinstance(pipeline_req, CoreReq)
        assert pipeline_req.word_target == expected
        assert pipeline_req.mode == GenerationMode.EXTEND
