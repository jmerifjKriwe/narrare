"""Tests for writing/pipeline.py — stop signals, error handling, interactive mode.

Split from test_pipeline.py for RULE-04 compliance.

Covers:
1. Stop signal — stops mid-generation
2. Error handling — registry error preserves partial text
3. Interactive session mode — raises ValueError
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk
from narrare_core.shared.errors import WritingError
from narrare_core.writing import GenerationMode
from narrare_core.writing.models import GenerationRequest
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


@pytest.fixture()
def mock_registry() -> Any:
    reg = MagicMock(spec=["stream", "run"])
    return reg


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
    mock_registry: Any,
    mock_composer: Any,
    mock_assembler: Any,
    mock_processor: Any,
) -> WritingPipeline:
    return WritingPipeline(
        registry=mock_registry,
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
        mock_registry: Any,
    ) -> None:
        request = _request(mode=GenerationMode.SCENE_BY_SCENE, outline="A scene")

        async def _streaming() -> AsyncIterator[StreamChunk]:
            for i in range(100):
                yield StreamChunk(text=f"chunk{i} ")
                if i == 3:
                    await pipeline.stop(request.id)

        mock_registry.stream = MagicMock(spec=[], return_value=_streaming())

        chunks = await _collect(
            pipeline.generate(request, config=_config()),
        )

        assert len(chunks) < 100

    @pytest.mark.asyncio
    async def test_stop_signal_cleaned_up(
        self,
        pipeline: WritingPipeline,
    ) -> None:
        """Stop signals are cleaned up after generation."""
        request = _request()

        with patch(
            "narrare_core.writing.pipeline_graph.stream_via_writing_graph",
        ) as mock_graph:

            async def fake_gen(*a: Any, **kw: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(text="done.", is_final=True)

            mock_graph.side_effect = lambda *a, **kw: fake_gen(a, kw)

            await _collect(pipeline.generate(request, config=_config()))

        assert request.id not in pipeline._stop_signals


class TestErrorHandling:
    """Registry errors in scene-by-scene mode are wrapped in WritingError."""

    @pytest.mark.asyncio
    async def test_scene_error_raises_writing_error(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        """Scene generation error is wrapped in WritingError."""
        mock_registry.stream = MagicMock(
            spec=[],
            side_effect=RuntimeError("Provider timeout"),
        )

        request = _request(
            mode=GenerationMode.SCENE_BY_SCENE,
            outline="A scene",
        )
        with pytest.raises(WritingError, match="Scene 1"):
            await _collect(
                pipeline.generate(request, config=_config()),
            )

    @pytest.mark.asyncio
    async def test_interview_error_raises_writing_error(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        mock_registry.run = AsyncMock(
            side_effect=RuntimeError("Service unavailable"),
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
