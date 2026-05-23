"""Tests for writing/pipeline.py — full draft, scene-by-scene, interview.

Split from test_pipeline.py for RULE-04 compliance.
Remaining tests in test_pipeline_errors.py.

Covers:
1. Full draft mode — delegates to WritingGraph
2. Scene-by-scene — generates scene by scene via registry.stream()
3. Interview-assisted — generates questions then returns via registry.run()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from narrare_core.llm.intents import LLMIntent, ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import (
    GenerationRequest,
    WritingContext,
)
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


def _default_context() -> WritingContext:
    return WritingContext(
        chapter_content="Previous content.",
        project_title="Test Novel",
        genre="fantasy",
        language="en",
        tone="balanced",
    )


async def _collect(iterator: AsyncIterator[StreamChunk]) -> list[StreamChunk]:
    chunks: list[StreamChunk] = []
    async for chunk in iterator:
        chunks.append(chunk)
    return chunks


async def _stream_from(*chunks: StreamChunk) -> AsyncIterator[StreamChunk]:
    """Yield chunks sequentially as an async generator."""
    for chunk in chunks:
        yield chunk


@pytest.fixture()
def mock_registry() -> Any:
    """Mock ModelRegistry with configurable stream/run."""
    reg = MagicMock(spec=["stream", "run"])
    return reg


@pytest.fixture()
def mock_composer() -> Any:
    """Mock PromptComposer returning a simple composed prompt."""
    comp = MagicMock(spec=PromptComposer)
    comp.build = AsyncMock(
        return_value=ComposedPrompt(system="sys prompt", user="user prompt"),
    )
    return comp


@pytest.fixture()
def mock_assembler() -> Any:
    """Mock WritingContextAssembler returning default context."""
    asm = MagicMock(spec=WritingContextAssembler)
    asm.assemble = AsyncMock(return_value=_default_context())
    return asm


@pytest.fixture()
def mock_processor() -> Any:
    """Mock DraftProcessor that returns text unchanged."""
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


class TestFullDraft:
    """Full draft mode delegates to WritingGraph."""

    @pytest.mark.asyncio
    async def test_delegates_to_writing_graph(
        self,
        pipeline: WritingPipeline,
    ) -> None:
        """Full draft always uses WritingGraph path."""
        with patch(
            "narrare_core.writing.pipeline_graph.stream_via_writing_graph",
        ) as mock_graph_stream:

            async def fake_gen(*a: Any, **kw: Any) -> AsyncIterator[StreamChunk]:
                yield StreamChunk(text="Hello World.", is_final=True)

            mock_graph_stream.side_effect = lambda *a, **kw: fake_gen(a, kw)

            chunks = await _collect(
                pipeline.generate(_request(), config=_config()),
            )

            mock_graph_stream.assert_called_once()
            assert any("Hello World." in c.text for c in chunks)


class TestSceneByScene:
    """Scene-by-scene generates each scene with break markers."""

    @pytest.mark.asyncio
    async def test_generates_each_scene(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        scene1_gen = _stream_from(
            StreamChunk(text="Scene one text."),
            StreamChunk(text="", is_final=True, usage=_usage()),
        )
        scene2_gen = _stream_from(
            StreamChunk(text="Scene two text."),
            StreamChunk(text="", is_final=True, usage=_usage()),
        )
        mock_registry.stream = MagicMock(
            spec=[],
            side_effect=[scene1_gen, scene2_gen],
        )

        outline = "1. First scene\n2. Second scene"
        request = _request(
            mode=GenerationMode.SCENE_BY_SCENE,
            outline=outline,
        )

        chunks = await _collect(
            pipeline.generate(request, config=_config()),
        )

        texts = [c.text for c in chunks]
        assert "Scene one text." in texts
        assert "Scene two text." in texts
        assert any("***" in t for t in texts)

    @pytest.mark.asyncio
    async def test_single_scene_no_separator(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_stream_from(
                StreamChunk(text="Only scene."),
                StreamChunk(text="", is_final=True, usage=_usage()),
            ),
        )

        request = _request(
            mode=GenerationMode.SCENE_BY_SCENE,
            outline="Single scene description",
        )

        chunks = await _collect(
            pipeline.generate(request, config=_config()),
        )

        texts = [c.text for c in chunks]
        assert "***" not in texts

    @pytest.mark.asyncio
    async def test_registry_stream_called_with_correct_intent(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        mock_registry.stream = MagicMock(
            spec=[],
            return_value=_stream_from(
                StreamChunk(text="", is_final=True, usage=_usage()),
            ),
        )

        request = _request(
            mode=GenerationMode.SCENE_BY_SCENE,
            outline="A scene",
        )
        await _collect(pipeline.generate(request, config=_config()))

        call_kwargs = mock_registry.stream.call_args
        assert call_kwargs.kwargs["intent"] == LLMIntent.WRITE


class TestInterviewAssisted:
    """Interview mode generates questions and returns them."""

    @pytest.mark.asyncio
    async def test_generates_questions(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        mock_registry.run = AsyncMock(
            return_value=(
                "1. What is the protagonist's motivation?\n2. Where does the story take place?"
            ),
        )

        request = _request(
            mode=GenerationMode.INTERVIEW_ASSISTED,
            outline="A detective story in Victorian London.",
        )

        chunks = await _collect(
            pipeline.generate(request, config=_config()),
        )

        assert len(chunks) == 2
        assert "protagonist" in chunks[0].text
        assert chunks[1].is_final

    @pytest.mark.asyncio
    async def test_uses_chat_intent(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        mock_registry.run = AsyncMock(
            return_value="Questions here.",
        )

        request = _request(mode=GenerationMode.INTERVIEW_ASSISTED)
        await _collect(pipeline.generate(request, config=_config()))

        call_args = mock_registry.run.call_args
        assert call_args.args[0] == LLMIntent.CHAT
