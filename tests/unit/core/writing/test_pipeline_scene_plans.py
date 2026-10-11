"""Tests for structured scene input on the scene-by-scene pipeline (PLAN-001 T9).

Covers spec §8.1: ``GenerationRequest.scenes`` present → each scene renders
via the shared renderer into per-scene ``author_instructions`` (no
``parse_scenes``); ``***`` separators and the final usage chunk stay
unchanged. Scenes absent (``None`` or empty) → the legacy
``parse_scenes(request.outline or context.chapter_outline)`` fallback.

The per-scene prompt input is captured at the existing stub seam: the mock
composer receives the full :class:`PromptContext` positionally
(``composer.build(intent, prompt_context)``), so ``author_instructions``
and the ``scene_number``/``total_scenes`` extras are inspectable per call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.result import StreamChunk, TokenUsage
from narrare_core.planning.models import ScenePlanData, ScenePresence, SceneStatus
from narrare_core.planning.scene_render import render_scene_for_prompt
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline
from narrare_core.writing.requests import SceneSpec, scene_spec_from_plan

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


def _spec(title: str, *, purpose: str = "", beats: tuple[str, ...] = ()) -> SceneSpec:
    return SceneSpec(title=title, purpose=purpose, beats=beats)


def _request(
    outline: str | None = None,
    scenes: tuple[SceneSpec, ...] | None = None,
) -> GenerationRequest:
    return GenerationRequest(
        chapter_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        mode=GenerationMode.SCENE_BY_SCENE,
        outline=outline,
        scenes=scenes,
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


def _scene_stream(text: str) -> Any:
    """One scene's registry stream: one text chunk + internal final usage."""
    return _stream_from(
        StreamChunk(text=text),
        StreamChunk(text="", is_final=True, usage=_usage()),
    )


@pytest.fixture()
def mock_registry() -> Any:
    """Mock ModelRegistry with configurable stream."""
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


def _composed_contexts(mock_composer: Any) -> list[Any]:
    """Extract the per-call PromptContext from the composer stub seam."""
    return [call.args[1] for call in mock_composer.build.call_args_list]


class TestScenesPresent:
    """request.scenes truthy → structured path (no parse_scenes)."""

    @pytest.mark.asyncio
    async def test_renders_per_scene_author_instructions(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
        mock_composer: Any,
    ) -> None:
        specs = (
            _spec("The Ambush", purpose="Reach the gate.", beats=("Horn",)),
            _spec("The Retreat", purpose="Escape.", beats=("Boat",)),
        )
        # Outline set too — proves parse_scenes output is NOT used.
        mock_registry.stream = MagicMock(
            spec=[],
            side_effect=[_scene_stream("A"), _scene_stream("B")],
        )
        request = _request(outline="1. First scene\n2. Second scene", scenes=specs)

        await _collect(pipeline.generate(request, config=_config()))

        contexts = _composed_contexts(mock_composer)
        assert len(contexts) == 2
        assert contexts[0].author_instructions == render_scene_for_prompt(specs[0], number=1)
        assert contexts[1].author_instructions == render_scene_for_prompt(specs[1], number=2)

    @pytest.mark.asyncio
    async def test_scene_number_and_total_scenes_from_tuple(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
        mock_composer: Any,
    ) -> None:
        specs = (_spec("One"), _spec("Two"), _spec("Three"))
        mock_registry.stream = MagicMock(
            spec=[],
            side_effect=[_scene_stream("A"), _scene_stream("B"), _scene_stream("C")],
        )
        request = _request(scenes=specs)

        await _collect(pipeline.generate(request, config=_config()))

        contexts = _composed_contexts(mock_composer)
        assert [c.extra["scene_number"] for c in contexts] == ["1", "2", "3"]
        assert {c.extra["total_scenes"] for c in contexts} == {"3"}

    @pytest.mark.asyncio
    async def test_separators_between_scenes_and_final_usage_unchanged(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        specs = (_spec("One"), _spec("Two"), _spec("Three"))
        mock_registry.stream = MagicMock(
            spec=[],
            side_effect=[_scene_stream("A"), _scene_stream("B"), _scene_stream("C")],
        )
        request = _request(scenes=specs)

        chunks = await _collect(pipeline.generate(request, config=_config()))

        texts = [c.text for c in chunks]
        assert texts == [
            "",  # context_meta chunk
            "A",
            "\n\n***\n\n",
            "B",
            "\n\n***\n\n",
            "C",
            "",
        ]
        finals = [c for c in chunks if c.is_final]
        assert len(finals) == 1
        assert finals[0].usage is not None
        assert finals[0].usage.prompt_tokens == 30
        assert finals[0].usage.completion_tokens == 150
        assert finals[0].usage.total_tokens == 180

    @pytest.mark.asyncio
    async def test_single_scene_no_separator(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
    ) -> None:
        mock_registry.stream = MagicMock(spec=[], side_effect=[_scene_stream("A")])
        request = _request(scenes=(_spec("Only"),))

        chunks = await _collect(pipeline.generate(request, config=_config()))

        assert not any("***" in c.text for c in chunks)


class TestScenesAbsent:
    """request.scenes falsy → legacy parse_scenes fallback intact."""

    @pytest.mark.asyncio
    async def test_none_scenes_parse_outline(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
        mock_composer: Any,
    ) -> None:
        mock_registry.stream = MagicMock(
            spec=[],
            side_effect=[_scene_stream("A"), _scene_stream("B")],
        )
        request = _request(outline="1. First scene\n2. Second scene")

        await _collect(pipeline.generate(request, config=_config()))

        contexts = _composed_contexts(mock_composer)
        # Legacy parse_scenes keeps the numbered markers (existing behavior).
        assert [c.author_instructions for c in contexts] == [
            "1. First scene",
            "2. Second scene",
        ]
        assert {c.extra["total_scenes"] for c in contexts} == {"2"}

    @pytest.mark.asyncio
    async def test_empty_tuple_scenes_falls_back(
        self,
        pipeline: WritingPipeline,
        mock_registry: Any,
        mock_composer: Any,
    ) -> None:
        mock_registry.stream = MagicMock(spec=[], side_effect=[_scene_stream("A")])
        request = _request(outline="Single scene description", scenes=())

        await _collect(pipeline.generate(request, config=_config()))

        contexts = _composed_contexts(mock_composer)
        assert len(contexts) == 1
        assert contexts[0].author_instructions == "Single scene description"


class TestSceneSpecFromPlan:
    """Core-internal adapter ScenePlanData → SceneSpec."""

    def test_maps_all_fields_and_presence_pairs(self) -> None:
        plan = ScenePlanData(
            id=uuid4(),
            position=2,
            title="The Ambush",
            pov_character_name="John Smith",
            location_name="The Castle",
            present_characters=(
                ScenePresence(name="John Smith", goal="warn the guard"),
                ScenePresence(name="Mara"),
            ),
            purpose="Reach the gate.",
            conflict="Mara blocks.",
            resolution="At a cost.",
            beats=("Horn",),
        )
        spec = scene_spec_from_plan(plan)
        assert spec == SceneSpec(
            title="The Ambush",
            pov_character_name="John Smith",
            location_name="The Castle",
            present_characters=(("John Smith", "warn the guard"), ("Mara", "")),
            purpose="Reach the gate.",
            conflict="Mara blocks.",
            resolution="At a cost.",
            beats=("Horn",),
            status="planned",
        )

    def test_status_value_becomes_plain_str(self) -> None:
        plan = ScenePlanData(id=uuid4(), position=1, title="S", status=SceneStatus.IN_PROGRESS)
        spec = scene_spec_from_plan(plan)
        assert spec.status == "in_progress"
        assert type(spec.status) is str

    def test_scene_status_member_maps_to_value(self) -> None:
        plan = ScenePlanData(id=uuid4(), position=1, title="S")
        assert scene_spec_from_plan(plan).status == "planned"
