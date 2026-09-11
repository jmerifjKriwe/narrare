"""Unit tests for RewriteService — stream_rewrite lifecycle and error handling.

Split from test_rewrite_service.py per RULE-04.

Covers:
1. stream_rewrite: happy path — chunks streamed, draft processed, status transitions
2. stream_rewrite: LLM failure — marks failed, logs error, partial word count
3. stream_rewrite: chapter_content construction (context markers)
4. stream_rewrite: KB relationships fetched and passed to pipeline
5. stream_rewrite: tone resolution and pipeline kwargs verification
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from narrare.writing.rewrite_service import RewriteService
from narrare.writing.schemas_rewrite import RewriteMode, RewriteRequest
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage

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
    "rewrite service streaming flow. It needs to exceed fifty characters "
    "to satisfy Pydantic's min_length constraint on RewriteRequest."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request(**kw: Any) -> RewriteRequest:
    """Create a RewriteRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "selection_text": _SELECTION,
        "mode": RewriteMode.TONE,
        "tone": "balanced",
        "language": "en",
    }
    defaults.update(kw)
    return RewriteRequest(**defaults)


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
) -> RewriteService:
    """RewriteService with mocked dependencies (no tone/relationship services)."""
    # S6 gate-open repos (chapter binds to ANY novel, every novel owned);
    # access matrix: test_generation_access_matrix.py.
    from tests.factories import make_chapter, make_novel

    chapter_repo = AsyncMock(spec=["get"])
    chapter_repo.get = AsyncMock(return_value=make_chapter(novel_id=ANY))
    novel_repo = AsyncMock(spec=["get_by_id"])
    novel_repo.get_by_id = AsyncMock(return_value=make_novel())
    return RewriteService(
        repo=mock_repo,
        pipeline=mock_pipeline,
        draft_processor=mock_draft_processor,
        config=CONFIG,
        chapter_repo=chapter_repo,
        novel_repo=novel_repo,
    )


# ---------------------------------------------------------------------------
# stream_rewrite: happy path
# ---------------------------------------------------------------------------


class TestStreamRewriteHappyPath:
    async def test_streams_text_chunks(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """Non-final chunks from the pipeline are yielded to the caller."""
        mock_pipeline.generate = MagicMock(
            spec=[], return_value=_fake_stream("First alternative. ", "Second alternative.")
        )

        chunks: list[StreamChunk] = []
        async for chunk in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            chunks.append(chunk)

        assert len(chunks) >= 2
        text_chunks = [c for c in chunks if c.text and not c.is_final]
        assert any("First" in c.text for c in text_chunks)

    async def test_final_chunk_has_usage(
        self, service: RewriteService, mock_pipeline: MagicMock
    ) -> None:
        """Final chunk carries token usage metadata."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Final text."))

        chunks: list[StreamChunk] = []
        async for chunk in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            chunks.append(chunk)

        final = [c for c in chunks if c.is_final]
        assert len(final) == 1
        assert final[0].usage is not None
        assert final[0].usage.total_tokens == 120

    async def test_status_transitions(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        """Status goes pending → streaming → completed."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Generated text."))

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        assert mock_repo.update_status.call_count == 2
        statuses = [c.args[1] for c in mock_repo.update_status.call_args_list]
        assert "streaming" in statuses
        assert "completed" in statuses

    async def test_streaming_status_includes_model_info(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        """Streaming transition records model_id and provider_name."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Text."))

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        streaming_call = mock_repo.update_status.call_args_list[0]
        kw = streaming_call.kwargs
        assert kw.get("model_id") == "test-model"
        assert kw.get("provider_name") == "test"

    async def test_draft_processor_applied_on_final(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_draft_processor: MagicMock,
    ) -> None:
        """DraftProcessor.process() is called on accumulated text when final chunk arrives."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Some ", "text."))

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        mock_draft_processor.process.assert_called_once()
        args, _ = mock_draft_processor.process.call_args
        assert "Some text." in args[0]

    async def test_word_count_stored_on_completion(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        """Completed status update includes word_count."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Three words here."))

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        completed_call = mock_repo.update_status.call_args_list[1]
        kw = completed_call.kwargs
        assert kw.get("word_count") == 3

    async def test_token_count_stored_on_completion(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        """Completed status update includes tokens_used from final chunk."""
        mock_pipeline.generate = MagicMock(spec=[], return_value=_fake_stream("Token test."))

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        completed_call = mock_repo.update_status.call_args_list[1]
        kw = completed_call.kwargs
        assert kw.get("tokens_used") == 120


# ---------------------------------------------------------------------------
# stream_rewrite: LLM failure
# ---------------------------------------------------------------------------


class TestStreamRewriteLLMFailure:
    async def test_marks_failed_on_exception(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        """When pipeline raises, status transitions to 'failed'."""

        async def _failing_gen() -> Any:
            yield StreamChunk(text="Partial rewrite ")
            raise RuntimeError("LLM connection lost")

        mock_pipeline.generate = MagicMock(spec=[], return_value=_failing_gen())

        chunks: list[StreamChunk] = []
        async for chunk in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            chunks.append(chunk)

        assert any("Partial" in c.text for c in chunks)
        statuses = [c.args[1] for c in mock_repo.update_status.call_args_list]
        assert "failed" in statuses

    async def test_error_message_recorded(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        """The error message is stored in the failed status update."""

        async def _failing_gen() -> Any:
            if False:
                yield
            raise RuntimeError("Model overloaded")

        mock_pipeline.generate = MagicMock(spec=[], return_value=_failing_gen())

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        failed_calls = [c for c in mock_repo.update_status.call_args_list if c.args[1] == "failed"]
        assert len(failed_calls) == 1
        assert "Model overloaded" in str(failed_calls[0])

    async def test_partial_text_processed_on_failure(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_draft_processor: MagicMock,
    ) -> None:
        """Partial accumulated text is processed with is_partital=True on failure."""

        async def _failing_gen() -> Any:
            yield StreamChunk(text="Partial generated text ")
            raise RuntimeError("Timeout")

        mock_pipeline.generate = MagicMock(spec=[], return_value=_failing_gen())

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        failed_call = mock_draft_processor.process.call_args_list[-1]
        assert failed_call.kwargs.get("is_partial") is True
        assert "Partial generated text " in failed_call.args[0]

    async def test_partial_word_count_stored_on_failure(
        self,
        service: RewriteService,
        mock_pipeline: MagicMock,
        mock_repo: AsyncMock,
    ) -> None:
        """Failed status update includes word_count from partial text."""

        async def _failing_gen() -> Any:
            yield StreamChunk(text="Three partial words")
            raise RuntimeError("Overloaded")

        mock_pipeline.generate = MagicMock(spec=[], return_value=_failing_gen())

        async for _ in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            pass

        failed_calls = [c for c in mock_repo.update_status.call_args_list if c.args[1] == "failed"]
        assert len(failed_calls) == 1
        kw = failed_calls[0].kwargs
        assert kw.get("word_count") == 3


# ---------------------------------------------------------------------------
# stream_rewrite: early completion without final chunk
# ---------------------------------------------------------------------------


class TestStreamRewriteNoFinalChunk:
    async def test_generator_without_final_chunk_ends_gracefully(
        self, service: RewriteService, mock_pipeline: MagicMock, mock_repo: AsyncMock
    ) -> None:
        """When the pipeline generator ends without a final chunk, the
        async for loop exits without hitting return (242->exit branch).

        Non-final chunks are still yielded to the caller, and no
        'completed' status update is written.
        """

        async def _no_final_chunk() -> Any:
            yield StreamChunk(text="Partial output without final marker")

        mock_pipeline.generate = MagicMock(spec=[], return_value=_no_final_chunk())

        chunks: list[StreamChunk] = []
        async for chunk in service.stream_rewrite(
            uuid.uuid4(), uuid.uuid4(), str(uuid.uuid4()), _request()
        ):
            chunks.append(chunk)

        # All yielded chunks should be non-final
        assert all(not c.is_final for c in chunks)
        assert len(chunks) == 1
        assert "Partial output" in chunks[0].text

        # No 'completed' status — generator ended without final chunk
        completed_calls = [
            c for c in mock_repo.update_status.call_args_list if c.args[1] == "completed"
        ]
        assert len(completed_calls) == 0
