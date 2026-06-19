"""Tests for invocation wiring across writing sub-pipelines (part 2).

Sub-pipelines covered here:
4. ``stream_scene_by_scene`` — pipeline_scene.py
5. ``stream_interview_assisted`` — pipeline_interview.py
6. Cross-cutting ``user_id``/``project_id`` pass-through (all 5 modes).

See: ADR-040 Decision 4, INFRA-013, CONSTRAINTS.md RULE-10/RULE-11.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.writing import GenerationMode
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from tests.unit.core.writing._invocation_helpers import (
    CONFIG,
    FakeEvidenceSink,
    _collect,
    _ctx,
    _make_pipeline,
    _mock_pipeline_with_sink,
    _req,
    _setup_run,
    _setup_stream,
)

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


# ===========================================================================
# 4. stream_scene_by_scene — pipeline_scene.py
# ===========================================================================


class TestSceneBySceneInvocationWiring:
    """stream_scene_by_scene produces evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_with_pipeline_produces_evidence(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Scene text.")
        req = _req(GenerationMode.SCENE_BY_SCENE, outline="A hero enters.")
        chunks = await _collect(pipeline.generate(req, config=CONFIG))
        assert any(c.is_final for c in chunks)
        assert len(sink.records) >= 1

    @pytest.mark.asyncio
    async def test_without_pipeline_behaves_identically(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=None,
        )
        _setup_stream(mock_registry, "Scene text.")
        req = _req(GenerationMode.SCENE_BY_SCENE, outline="A hero enters.")
        chunks = await _collect(pipeline.generate(req, config=CONFIG))
        assert any(c.is_final for c in chunks)
        assert mock_composer.build.call_count >= 1

    @pytest.mark.asyncio
    async def test_evidence_has_correct_intent(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Text.")
        req = _req(GenerationMode.SCENE_BY_SCENE, outline="Scene one.")
        await _collect(pipeline.generate(req, config=CONFIG))
        assert sink.records[0].feature_id == "writing_write"

    @pytest.mark.asyncio
    async def test_multi_scene_produces_evidence_per_scene(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_stream(mock_registry, "Scene text.")

        req = _req(
            GenerationMode.SCENE_BY_SCENE,
            outline="Scene 1.\n***\nScene 2.\n***\nScene 3.",
        )
        chunks = await _collect(pipeline.generate(req, config=CONFIG))
        assert any(c.is_final for c in chunks)
        assert len(sink.records) == 3


# ===========================================================================
# 5. stream_interview_assisted — pipeline_interview.py
# ===========================================================================


class TestInterviewInvocationWiring:
    """stream_interview_assisted produces evidence when invocation_pipeline is wired."""

    @pytest.mark.asyncio
    async def test_with_pipeline_produces_evidence(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_run(mock_registry, "What is the main conflict?")
        chunks = await _collect(
            pipeline.generate(_req(GenerationMode.INTERVIEW_ASSISTED), config=CONFIG),
        )
        assert any(c.is_final for c in chunks)
        assert len(sink.records) == 1

    @pytest.mark.asyncio
    async def test_without_pipeline_behaves_identically(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=None,
        )
        _setup_run(mock_registry, "What is the main conflict?")
        chunks = await _collect(
            pipeline.generate(_req(GenerationMode.INTERVIEW_ASSISTED), config=CONFIG),
        )
        assert any(c.is_final for c in chunks)
        assert mock_composer.build.call_count == 1

    @pytest.mark.asyncio
    async def test_evidence_has_correct_intent(
        self,
        mock_registry: Any,
        mock_composer: Any,
        mock_assembler: Any,
        mock_processor: Any,
    ) -> None:
        sink = FakeEvidenceSink()
        pipeline = _make_pipeline(
            mock_registry,
            mock_composer,
            mock_assembler,
            mock_processor,
            invocation_pipeline=_mock_pipeline_with_sink(sink),
        )
        _setup_run(mock_registry, "Question?")
        await _collect(
            pipeline.generate(_req(GenerationMode.INTERVIEW_ASSISTED), config=CONFIG),
        )
        assert sink.records[0].feature_id == "writing_chat"


# Cross-cutting user_id/project_id pass-through tests live in
# ``test_invocation_user_id_passthrough.py`` (split per RULE-04).
