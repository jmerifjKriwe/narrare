"""Tests for writing/pipeline_extend.py — extend generation mode.

Covers:
1. EXTEND dispatch — ``generate()`` routes to ``stream_extend()``
2. Word target — ``request.word_target`` used, falls back to 400
3. Prompt context — ``mode="extend_chapter"``, ``existing_content`` with marker
4. DraftProcessor applied on final accumulated text
5. Stop signal respected mid-stream
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIG = ResolvedModelConfig(provider_name="test", model_id="test-model", max_tokens=2000)
USAGE = TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


def _req(**kw: Any) -> GenerationRequest:
    defaults: dict[str, Any] = {
        "chapter_id": uuid4(),
        "project_id": uuid4(),
        "user_id": uuid4(),
        "mode": GenerationMode.EXTEND,
    }
    defaults.update(kw)
    return GenerationRequest(**defaults)


def _ctx(chapter_content: str = "", **kw: Any) -> WritingContext:
    defaults: dict[str, Any] = {
        "chapter_content": chapter_content,
        "project_title": "Test Novel",
        "genre": "fantasy",
        "language": "en",
        "tone": "balanced",
        "writing_language": "English",
    }
    defaults.update(kw)
    return WritingContext(**defaults)


async def _collect(gen: Any) -> list[StreamChunk]:
    out: list[StreamChunk] = []
    async for c in gen:
        out.append(c)
    return out


async def _stream(*chunks: StreamChunk):  # type: ignore[no-untyped-def]
    for c in chunks:
        yield c


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_registry() -> Any:
    return MagicMock(spec=["stream", "run"])


@pytest.fixture()
def mock_composer() -> Any:
    comp = MagicMock(spec=PromptComposer)
    comp.build = AsyncMock(return_value=ComposedPrompt(system="sys", user="usr"))
    return comp


@pytest.fixture()
def mock_assembler() -> Any:
    asm = MagicMock(spec=WritingContextAssembler)
    asm.assemble = AsyncMock(return_value=_ctx())
    return asm


@pytest.fixture()
def mock_processor() -> Any:
    proc = MagicMock(spec=DraftProcessor)
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return proc


@pytest.fixture()
def pipeline(
    mock_registry: Any, mock_composer: Any, mock_assembler: Any, mock_processor: Any
) -> WritingPipeline:
    return WritingPipeline(
        registry=mock_registry,
        composer=mock_composer,
        context_assembler=mock_assembler,
        draft_processor=mock_processor,
    )


def _setup_stream(mock_registry: Any, *texts: str) -> None:
    """Wire mock_registry.stream to yield text chunks + final chunk."""
    chunks = [StreamChunk(text=t) for t in texts]
    chunks.append(StreamChunk(text="", is_final=True, usage=USAGE))
    mock_registry.stream = MagicMock(spec=[], return_value=_stream(*chunks))


# ---------------------------------------------------------------------------
# Dispatch + Intent
# ---------------------------------------------------------------------------


class TestDispatch:
    @pytest.mark.asyncio
    async def test_routes_to_extend(self, pipeline: WritingPipeline, mock_registry: Any) -> None:
        _setup_stream(mock_registry, "Continuation text.")
        chunks = await _collect(pipeline.generate(_req(), config=CONFIG))
        assert chunks[0].context_meta is not None  # CR-07 metadata
        assert any("Continuation text." in c.text for c in chunks)
        assert any(c.is_final for c in chunks)

    @pytest.mark.asyncio
    async def test_uses_llm_intent_extend(
        self, pipeline: WritingPipeline, mock_registry: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(pipeline.generate(_req(), config=CONFIG))
        assert mock_registry.stream.call_args.kwargs["intent"] == LLMIntent.EXTEND


# ---------------------------------------------------------------------------
# Word target
# ---------------------------------------------------------------------------


class TestWordTarget:
    @pytest.mark.asyncio
    async def test_from_request(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(pipeline.generate(_req(word_target=200), config=CONFIG))
        ctx = mock_composer.build.call_args.args[1]
        assert ctx.extra["word_target"] == "200"
        assert ctx.extra["extend_length"] == "200"

    @pytest.mark.asyncio
    async def test_defaults_to_400(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(pipeline.generate(_req(), config=CONFIG))
        ctx = mock_composer.build.call_args.args[1]
        assert ctx.extra["word_target"] == "400"
        assert ctx.extra["extend_length"] == "400"


# ---------------------------------------------------------------------------
# PromptContext construction
# ---------------------------------------------------------------------------


class TestPromptContext:
    @pytest.mark.asyncio
    async def test_mode_is_extend_chapter(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(pipeline.generate(_req(), config=CONFIG))
        assert mock_composer.build.call_args.args[1].mode == "extend_chapter"

    @pytest.mark.asyncio
    async def test_intent_is_extend(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(pipeline.generate(_req(), config=CONFIG))
        assert mock_composer.build.call_args.args[0] == LLMIntent.EXTEND

    @pytest.mark.asyncio
    async def test_existing_content_has_marker(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
    ) -> None:
        combined = "Pre-text\n[CONTINUE FROM HERE]\nPost-text"
        mock_assembler.assemble = AsyncMock(return_value=_ctx(chapter_content=combined))
        _setup_stream(mock_registry)
        await _collect(pipeline.generate(_req(), config=CONFIG))
        ec = mock_composer.build.call_args.args[1].existing_content
        assert "Pre-text" in ec
        assert "[CONTINUE FROM HERE]" in ec
        assert "Post-text" in ec


# ---------------------------------------------------------------------------
# Streaming + DraftProcessor
# ---------------------------------------------------------------------------


class TestStreamingAndProcessor:
    @pytest.mark.asyncio
    async def test_draft_processor_applied(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_processor: Any
    ) -> None:
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_stream(
                StreamChunk(text="Hello "),
                StreamChunk(text="World."),
                StreamChunk(text="", is_final=True, usage=USAGE),
            ),
        )
        chunks = await _collect(pipeline.generate(_req(), config=CONFIG))
        mock_processor.process.assert_called_once_with("Hello World.", word_target=400)
        assert any(c.is_final and c.usage for c in chunks)

    @pytest.mark.asyncio
    async def test_intermediate_chunks_streamed(
        self, pipeline: WritingPipeline, mock_registry: Any
    ) -> None:
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_stream(
                StreamChunk(text="First "),
                StreamChunk(text="Second "),
                StreamChunk(text="Third."),
                StreamChunk(text="", is_final=True, usage=USAGE),
            ),
        )
        chunks = await _collect(pipeline.generate(_req(), config=CONFIG))
        text_chunks = [c for c in chunks if c.text and not c.is_final]
        assert [c.text for c in text_chunks] == ["First ", "Second ", "Third."]


# ---------------------------------------------------------------------------
# Stop signal
# ---------------------------------------------------------------------------


class TestStopSignal:
    @pytest.mark.asyncio
    async def test_stop_halts_streaming(
        self, pipeline: WritingPipeline, mock_registry: Any
    ) -> None:
        _setup_stream(mock_registry, "First.", "Second.")
        req = _req()
        await pipeline.stop(req.id)
        chunks = await _collect(pipeline.generate(req, config=CONFIG))
        # stream_extend checks _is_stopped — no text chunks yielded
        assert not any(c.text for c in chunks)
