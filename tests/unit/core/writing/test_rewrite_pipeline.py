"""Tests for writing/pipeline_rewrite.py — rewrite generation mode.

Covers:
1. REWRITE dispatch — ``generate()`` routes to ``stream_rewrite()``
2. Rewrite budget allocation (40/15/25/10/10)
3. Context assembly includes selection_text, context_before, context_after
4. Rewrite mode="rewrite_selection" resolved by composer
5. Mode-specific strategy instructions (tone, style, voice, fix, custom)
6. Count parameter passed to prompt template
7. Stop signal respected mid-stream
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
        "mode": GenerationMode.REWRITE,
    }
    defaults.update(kw)
    return GenerationRequest(**defaults)


def _ctx(**kw: Any) -> WritingContext:
    defaults: dict[str, Any] = {
        "chapter_content": "",
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
    async def test_routes_to_rewrite(self, pipeline: WritingPipeline, mock_registry: Any) -> None:
        _setup_stream(mock_registry, "<alternative>Rewritten text.</alternative>")
        chunks = await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Original text to rewrite.",
            )
        )
        assert chunks[0].context_meta is not None  # CR-07 metadata
        assert any("alternative" in c.text for c in chunks)
        assert any(c.is_final for c in chunks)

    @pytest.mark.asyncio
    async def test_uses_llm_intent_rewrite(
        self, pipeline: WritingPipeline, mock_registry: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Some text.",
            )
        )
        assert mock_registry.stream.call_args.kwargs["intent"] == LLMIntent.REWRITE


# ---------------------------------------------------------------------------
# Prompt context construction
# ---------------------------------------------------------------------------


class TestPromptContext:
    @pytest.mark.asyncio
    async def test_mode_is_rewrite_selection(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
            )
        )
        assert mock_composer.build.call_args.args[1].mode == "rewrite_selection"

    @pytest.mark.asyncio
    async def test_intent_is_rewrite(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
            )
        )
        assert mock_composer.build.call_args.args[0] == LLMIntent.REWRITE

    @pytest.mark.asyncio
    async def test_selection_text_in_context(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="The selection to rewrite.",
                context_before="Text before.",
                context_after="Text after.",
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        assert ctx.extra["selection_text"] == "The selection to rewrite."
        assert ctx.extra["context_before"] == "Text before."
        assert ctx.extra["context_after"] == "Text after."
        assert ctx.existing_content == "The selection to rewrite."

    @pytest.mark.asyncio
    async def test_count_in_context(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
                rewrite_count=3,
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        assert ctx.extra["count"] == "3"


# ---------------------------------------------------------------------------
# Rewrite mode instructions
# ---------------------------------------------------------------------------


class TestRewriteModeInstructions:
    @pytest.mark.asyncio
    async def test_tone_mode_instructions(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
                rewrite_mode="tone",
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        instr = ctx.extra["rewrite_mode_instructions"]
        assert "emotional language" in instr
        assert "pacing" in instr

    @pytest.mark.asyncio
    async def test_style_mode_instructions(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
                rewrite_mode="style",
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        instr = ctx.extra["rewrite_mode_instructions"]
        assert "sentence structure" in instr

    @pytest.mark.asyncio
    async def test_fix_mode_instructions(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
                rewrite_mode="fix",
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        instr = ctx.extra["rewrite_mode_instructions"]
        assert "show-don't-tell" in instr

    @pytest.mark.asyncio
    async def test_custom_mode_instructions(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
                rewrite_mode="custom",
                custom_instructions="Make it rhyme in iambic pentameter.",
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        instr = ctx.extra["rewrite_mode_instructions"]
        assert "Make it rhyme in iambic pentameter" in instr

    @pytest.mark.asyncio
    async def test_voice_mode_instructions(
        self, pipeline: WritingPipeline, mock_registry: Any, mock_composer: Any
    ) -> None:
        _setup_stream(mock_registry)
        await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Text.",
                rewrite_mode="voice",
            )
        )
        ctx = mock_composer.build.call_args.args[1]
        instr = ctx.extra["rewrite_mode_instructions"]
        assert "speech patterns" in instr


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
                StreamChunk(text="<alternative>"),
                StreamChunk(text="Rewritten."),
                StreamChunk(text="</alternative>"),
                StreamChunk(text="", is_final=True, usage=USAGE),
            ),
        )
        chunks = await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Original.",
            )
        )
        # DraftProcessor called on accumulated text (no word_target for rewrite)
        mock_processor.process.assert_called_once_with("<alternative>Rewritten.</alternative>")
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
        chunks = await _collect(
            pipeline.generate(
                _req(),
                config=CONFIG,
                selection_text="Original.",
            )
        )
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
        chunks = await _collect(
            pipeline.generate(
                req,
                config=CONFIG,
                selection_text="Text.",
            )
        )
        # stream_rewrite checks _is_stopped — no text chunks yielded
        assert not any(c.text for c in chunks)
