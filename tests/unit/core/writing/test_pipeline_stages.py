"""Stage-level tests for WritingPipeline.generate()'s extracted stages.

Covers the single-responsibility stage helpers introduced by AUFG-01-08,
extracted into :mod:`narrare_core.writing._stages` (RULE-04):

1. :func:`narrare_core.writing._stages.resolve_voice_profile_consumer` (Stage 1)
2. :func:`narrare_core.writing._stages.assemble_writing_context` (Stage 2)

The Stage-4 dispatch (:func:`narrare_core.writing._mode_dispatch.stream_for_mode`)
is covered behaviourally by the per-mode test modules (test_pipeline.py,
test_pipeline_graph.py, test_extend_pipeline.py, test_rewrite_pipeline.py,
test_pipeline_coauthor*.py) and is intentionally not duplicated here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from narrare_core.profiles.contracts import VoiceProfileConsumer
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing._stages import (
    assemble_writing_context,
    resolve_voice_profile_consumer,
)
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationRequest, WritingContext
from narrare_core.writing.pipeline import WritingPipeline


def _entity() -> KBEntity:
    return KBEntity(
        entity_id="e1",
        entity_type="character",
        name="Aria",
        content="A brave hero.",
    )


def _request() -> GenerationRequest:
    return GenerationRequest(
        chapter_id=uuid4(),
        project_id=uuid4(),
        user_id=uuid4(),
        mode=GenerationMode.FULL_DRAFT,
    )


def _make_pipeline(*, voice_factory: Any = None) -> WritingPipeline:
    """Build a WritingPipeline with a mock assembler whose calls can be inspected."""
    assembler = MagicMock(spec=WritingContextAssembler)
    assembler.assemble = AsyncMock(return_value=WritingContext())
    composer = MagicMock(spec=PromptComposer)
    composer.build = AsyncMock(
        return_value=ComposedPrompt(system="sys", user="user"),
    )
    return WritingPipeline(
        registry=MagicMock(spec=["stream", "run"]),
        composer=composer,
        context_assembler=assembler,
        draft_processor=MagicMock(spec=DraftProcessor),
        voice_profile_consumer_factory=voice_factory,
    )


class TestResolveVoiceProfileConsumer:
    """Stage 1 — voice-profile consumer resolution."""

    def test_no_factory_returns_none(self) -> None:
        """Without a wired factory, profiling is disabled regardless of entities."""
        pipeline = _make_pipeline()
        assert resolve_voice_profile_consumer(pipeline, [_entity()]) is None

    def test_factory_with_entities_returns_consumer(self) -> None:
        """Factory + non-empty entities → consumer built from those entities."""
        consumer: Any = MagicMock(spec=VoiceProfileConsumer, name="VoiceProfileConsumer")
        factory: Any = MagicMock(spec=Callable, return_value=consumer)
        pipeline = _make_pipeline(voice_factory=factory)

        entities = [_entity()]
        result = resolve_voice_profile_consumer(pipeline, entities)

        assert result is consumer
        factory.assert_called_once_with(entities)

    def test_factory_without_entities_returns_none(self) -> None:
        """Factory + ``None`` entities → no consumer, factory not invoked."""
        factory: Any = MagicMock(spec=Callable, return_value=MagicMock(spec=VoiceProfileConsumer))
        pipeline = _make_pipeline(voice_factory=factory)

        assert resolve_voice_profile_consumer(pipeline, None) is None
        factory.assert_not_called()

    def test_factory_with_empty_entities_returns_none(self) -> None:
        """Factory + empty entity list → no consumer (truthiness guard)."""
        factory: Any = MagicMock(spec=Callable, return_value=MagicMock(spec=VoiceProfileConsumer))
        pipeline = _make_pipeline(voice_factory=factory)

        assert resolve_voice_profile_consumer(pipeline, []) is None
        factory.assert_not_called()


class TestAssembleWritingContext:
    """Stage 2 — context assembly (delegates to WritingContextAssembler)."""

    @pytest.mark.asyncio
    async def test_forwards_request_and_context_params(self) -> None:
        """Request-derived fields are mapped; call-level inputs forwarded verbatim."""
        pipeline = _make_pipeline()
        assembler: Any = pipeline._context_assembler
        consumer: Any = MagicMock(spec=VoiceProfileConsumer, name="VoiceProfileConsumer")
        request = _request()

        await assemble_writing_context(
            pipeline,
            request,
            voice_profile_consumer=consumer,
            chapter_content="Existing text.",
            chapter_frontmatter="# Ch 1",
            chapter_outline="Outline notes",
            recent_chapters=None,
            kb_entities=[_entity()],
            entity_connections={"a": {"b"}},
            kb_relationships="Aria → ally → Marcus",
            project_title="Test Novel",
            genre="fantasy",
            user_preferences="Avoid adverbs.",
            avoidance_patterns="cliché",
        )

        assembler.assemble.assert_awaited_once()
        kwargs = assembler.assemble.call_args.kwargs
        # Request-derived fields are mapped, not passed verbatim.
        assert kwargs["project_id"] == request.project_id
        assert kwargs["language"] == request.writing_language
        assert kwargs["writing_language"] == request.writing_language
        assert kwargs["tone"] == request.tone
        assert kwargs["word_target"] == request.word_target
        assert kwargs["mode"] == str(request.mode)
        assert kwargs["voice_profile_consumer"] is consumer
        # Call-level context inputs forwarded unchanged.
        assert kwargs["chapter_content"] == "Existing text."
        assert kwargs["entity_connections"] == {"a": {"b"}}
        assert kwargs["kb_relationships"] == "Aria → ally → Marcus"
        assert kwargs["genre"] == "fantasy"

    @pytest.mark.asyncio
    async def test_forwards_cross_session_context(self) -> None:
        """cross_session_context is forwarded verbatim to the assembler."""
        pipeline = _make_pipeline()
        assembler: Any = pipeline._context_assembler
        request = _request()

        await assemble_writing_context(
            pipeline,
            request,
            voice_profile_consumer=None,
            chapter_content="",
            chapter_frontmatter="",
            chapter_outline="",
            recent_chapters=None,
            kb_entities=None,
            entity_connections=None,
            kb_relationships="",
            project_title="",
            genre="",
            user_preferences="",
            avoidance_patterns="",
            cross_session_context="- Author likes short chapters.",
        )

        kwargs = assembler.assemble.call_args.kwargs
        assert kwargs["cross_session_context"] == "- Author likes short chapters."

    @pytest.mark.asyncio
    async def test_cross_session_context_defaults_empty(self) -> None:
        """When omitted, cross_session_context defaults to empty string."""
        pipeline = _make_pipeline()
        assembler: Any = pipeline._context_assembler
        request = _request()

        await assemble_writing_context(
            pipeline,
            request,
            voice_profile_consumer=None,
            chapter_content="",
            chapter_frontmatter="",
            chapter_outline="",
            recent_chapters=None,
            kb_entities=None,
            entity_connections=None,
            kb_relationships="",
            project_title="",
            genre="",
            user_preferences="",
            avoidance_patterns="",
        )

        kwargs = assembler.assemble.call_args.kwargs
        assert kwargs["cross_session_context"] == ""

    @pytest.mark.asyncio
    async def test_returns_assembled_context(self) -> None:
        """The assembler's return value is returned unchanged (pure delegation)."""
        assembled = WritingContext(chapter_content="ctx", project_title="P")
        assembler = MagicMock(spec=WritingContextAssembler)
        assembler.assemble = AsyncMock(return_value=assembled)
        pipeline = WritingPipeline(
            registry=MagicMock(spec=["stream", "run"]),
            composer=MagicMock(spec=PromptComposer),
            context_assembler=assembler,
            draft_processor=MagicMock(spec=DraftProcessor),
        )

        result = await assemble_writing_context(
            pipeline,
            _request(),
            voice_profile_consumer=None,
            chapter_content="",
            chapter_frontmatter="",
            chapter_outline="",
            recent_chapters=None,
            kb_entities=None,
            entity_connections=None,
            kb_relationships="",
            project_title="",
            genre="",
            user_preferences="",
            avoidance_patterns="",
        )

        assert result is assembled
