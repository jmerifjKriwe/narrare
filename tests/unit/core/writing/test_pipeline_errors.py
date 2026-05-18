"""Tests for writing/pipeline.py — stop signals, error handling, interactive mode.

Split from test_pipeline.py for RULE-04 compliance.

Covers:
1. Stop signal — stops mid-generation
2. Error handling — gateway error preserves partial text
3. Interactive session mode — raises ValueError
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.shared.errors import LLMGatewayError, WritingError
from narrare_core.writing.models import GenerationMode, GenerationRequest
from narrare_core.writing.pipeline import WritingPipeline

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test",
        model_id="test-model",
        temperature=0.7,
        max_tokens=2000,
        streams=True,
    )


def _usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=10, completion_tokens=50, total_tokens=60)


def _request(
    mode: GenerationMode = GenerationMode.FULL_DRAFT,
    outline: str | None = None,
    prompt: str | None = None,
) -> GenerationRequest:
    return GenerationRequest(
        chapter_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        mode=mode,
        outline=outline,
        prompt=prompt,
    )


async def _collect(iterator: AsyncIterator[StreamChunk]) -> list[StreamChunk]:
    chunks: list[StreamChunk] = []
    async for chunk in iterator:
        chunks.append(chunk)
    return chunks


async def _stream_from(*chunks: StreamChunk) -> AsyncIterator[StreamChunk]:
    for chunk in chunks:
        yield chunk


@pytest.fixture()
def mock_gateway() -> Any:
    gw = MagicMock(spec=["stream", "run"])
    return gw


@pytest.fixture()
def mock_composer() -> Any:
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer

    comp = MagicMock(spec=PromptComposer)
    comp.build = AsyncMock(
        return_value=ComposedPrompt(system="sys prompt", user="user prompt"),
    )
    return comp


@pytest.fixture()
def mock_assembler() -> Any:
    from narrare_core.writing.context_assembler import WritingContextAssembler
    from narrare_core.writing.models import WritingContext

    asm = MagicMock(spec=WritingContextAssembler)
    asm.assemble = AsyncMock(return_value=WritingContext())
    return asm


@pytest.fixture()
def mock_processor() -> Any:
    from narrare_core.writing.draft_processor import DraftProcessor

    proc = MagicMock(spec=DraftProcessor)
    proc.process = MagicMock(spec=[], side_effect=lambda text, **kw: text)
    return proc


@pytest.fixture()
def pipeline(
    mock_gateway: Any,
    mock_composer: Any,
    mock_assembler: Any,
    mock_processor: Any,
) -> WritingPipeline:
    return WritingPipeline(
        gateway=mock_gateway,
        composer=mock_composer,
        context_assembler=mock_assembler,
        draft_processor=mock_processor,
    )


class TestStopSignal:
    """Stop signal halts generation mid-stream."""

    @pytest.mark.asyncio
    async def test_stop_halts_generation(
        self,
        pipeline: WritingPipeline,
        mock_gateway: Any,
    ) -> None:
        request = _request()

        async def _streaming() -> AsyncIterator[StreamChunk]:
            for i in range(100):
                yield StreamChunk(text=f"chunk{i} ")
                if i == 3:
                    await pipeline.stop(request.id)

        mock_gateway.stream = MagicMock(spec=[], return_value=_streaming())

        chunks = await _collect(
            pipeline.generate(request, config=_config()),
        )

        assert len(chunks) < 100

    @pytest.mark.asyncio
    async def test_stop_signal_cleaned_up(
        self,
        pipeline: WritingPipeline,
        mock_gateway: Any,
    ) -> None:
        request = _request()

        mock_gateway.stream = MagicMock(
            spec=[],
            return_value=_stream_from(
                StreamChunk(text="done."),
                StreamChunk(text="", is_final=True, usage=_usage()),
            ),
        )

        await _collect(pipeline.generate(request, config=_config()))

        assert request.id not in pipeline._stop_signals


class TestErrorHandling:
    """Gateway errors are wrapped in WritingError."""

    @pytest.mark.asyncio
    async def test_gateway_error_raises_writing_error(
        self,
        pipeline: WritingPipeline,
        mock_gateway: Any,
    ) -> None:
        mock_gateway.stream = MagicMock(
            spec=[],
            side_effect=LLMGatewayError("Provider timeout", code="TIMEOUT"),
        )

        with pytest.raises(WritingError, match="Draft generation failed"):
            await _collect(
                pipeline.generate(_request(), config=_config()),
            )

    @pytest.mark.asyncio
    async def test_interview_error_raises_writing_error(
        self,
        pipeline: WritingPipeline,
        mock_gateway: Any,
    ) -> None:
        mock_gateway.run = AsyncMock(
            side_effect=LLMGatewayError("Service unavailable", code="SERVICE_UNAVAILABLE"),
        )

        request = _request(mode=GenerationMode.INTERVIEW_ASSISTED)
        with pytest.raises(WritingError, match="Interview"):
            await _collect(pipeline.generate(request, config=_config()))


class TestInteractiveSession:
    """Interactive session mode raises ValueError."""

    @pytest.mark.asyncio
    async def test_raises_value_error(self, pipeline: WritingPipeline) -> None:
        request = _request(mode=GenerationMode.INTERACTIVE_SESSION)

        with pytest.raises(ValueError, match="WebSocket"):
            await _collect(pipeline.generate(request, config=_config()))
