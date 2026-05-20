"""Tests für WritingPipeline-Integration mit WritingGraph.

Testet ob die Pipeline korrekt den WritingGraph-Pfad wählt
wenn use_writing_graph=True gesetzt ist.

Coverage-Ziel: pipeline_graph.py > 80%
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from narrare_core.llm.gateway import LLMGateway
from narrare_core.llm.result import StreamChunk
from narrare_core.prompts.composer import PromptComposer
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor
from narrare_core.writing.models import GenerationMode, GenerationRequest, WritingContext


def _make_pipeline(**flags: bool) -> Any:
    """Erstelle eine WritingPipeline mit gemockten Dependencies."""
    from narrare_core.writing.pipeline import WritingPipeline

    gateway = MagicMock(spec=LLMGateway)
    composer = MagicMock(spec=PromptComposer)
    context_assembler = MagicMock(spec=WritingContextAssembler)
    draft_processor = MagicMock(spec=DraftProcessor)
    registry = (
        MagicMock()
    )  # narrare: allow reason="ModelRegistry is Protocol — no concrete class for spec="
    return WritingPipeline(
        gateway=gateway,
        composer=composer,
        context_assembler=context_assembler,
        draft_processor=draft_processor,
        registry=registry,
        **flags,
    )


class TestPipelineWritingGraphFlag:
    """WritingPipeline + use_writing_graph Flag."""

    def test_pipeline_accepts_writing_graph_flag(self) -> None:
        pipeline = _make_pipeline(use_writing_graph=True)
        assert pipeline._use_writing_graph is True

    def test_pipeline_default_no_writing_graph(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline._use_writing_graph is False

    @pytest.mark.asyncio
    async def test_pipeline_graph_path_selected(self) -> None:
        """_full_draft delegiert an _stream_via_writing_graph wenn Flag gesetzt."""
        from uuid import uuid4

        pipeline = _make_pipeline(use_writing_graph=True)

        request = GenerationRequest(
            chapter_id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            mode=GenerationMode.FULL_DRAFT,
        )
        context = WritingContext()
        config = (
            MagicMock()
        )  # narrare: allow reason="ResolvedModelConfig is TypedDict — no concrete class for spec="

        chunks: list[Any] = []
        with patch.object(
            pipeline,
            "_stream_via_writing_graph",
            new_callable=MagicMock,
        ) as mock_stream:

            async def fake_gen(*a: Any, **kw: Any) -> Any:
                yield StreamChunk(text="done", is_final=True)

            mock_stream.side_effect = lambda *a, **kw: fake_gen(a, kw)

            async for chunk in pipeline._full_draft(request, context, config):
                chunks.append(chunk)

        mock_stream.assert_called_once()
        assert len(chunks) == 1
        assert chunks[0].text == "done"

    @pytest.mark.asyncio
    async def test_pipeline_draft_agent_fallback_without_graph_flag(self) -> None:
        """Wenn use_writing_graph=False, wird DraftAgent-Pfad gewählt wenn Registry gesetzt."""
        from uuid import uuid4

        pipeline = _make_pipeline(use_draft_agent=True, use_writing_graph=False)

        request = GenerationRequest(
            chapter_id=uuid4(),
            project_id=uuid4(),
            user_id=uuid4(),
            mode=GenerationMode.FULL_DRAFT,
        )
        context = WritingContext()
        config = (
            MagicMock()
        )  # narrare: allow reason="ResolvedModelConfig is TypedDict — no concrete class for spec="

        with patch.object(
            pipeline,
            "_stream_via_draft_agent",
            new_callable=MagicMock,
        ) as mock_stream:

            async def fake_gen(*a: Any, **kw: Any) -> Any:
                yield StreamChunk(text="draft agent output", is_final=True)

            mock_stream.side_effect = lambda *a, **kw: fake_gen(a, kw)

            chunks = []
            async for chunk in pipeline._full_draft(request, context, config):
                chunks.append(chunk)

        mock_stream.assert_called_once()
