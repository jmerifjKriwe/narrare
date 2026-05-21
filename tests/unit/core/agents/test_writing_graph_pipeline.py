"""Tests für WritingPipeline-Integration mit WritingGraph.

Testet ob die Pipeline korrekt den WritingGraph-Pfad wählt
(wird immer gewählt, keine Feature-Flags mehr).

Coverage-Ziel: pipeline_graph.py > 80%
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from narrare_core.llm.gateway import ModelRegistry
from narrare_core.llm.intents import ResolvedModelConfig
from narrare_core.prompts.composer import PromptComposer
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.draft_processor import DraftProcessor


def _make_pipeline() -> Any:
    """Erstelle eine WritingPipeline mit gemockten Dependencies."""
    from narrare_core.writing.pipeline import WritingPipeline

    registry = MagicMock(spec=ModelRegistry)
    composer = MagicMock(spec=PromptComposer)
    context_assembler = MagicMock(spec=WritingContextAssembler)
    draft_processor = MagicMock(spec=DraftProcessor)
    return WritingPipeline(
        registry=registry,
        composer=composer,
        context_assembler=context_assembler,
        draft_processor=draft_processor,
    )


class TestPipelineWritingGraph:
    """WritingPipeline always uses WritingGraph for full drafts."""

    def test_pipeline_has_registry(self) -> None:
        pipeline = _make_pipeline()
        assert pipeline._registry is not None

    @pytest.mark.asyncio
    async def test_pipeline_graph_path_selected(self) -> None:
        """_full_draft delegiert an stream_via_writing_graph."""
        from unittest.mock import patch
        from uuid import uuid4

        from narrare_core.llm.result import StreamChunk
        from narrare_core.writing.models import GenerationMode, GenerationRequest, WritingContext

        pipeline = _make_pipeline()

        with patch(
            "narrare_core.writing.pipeline_graph.stream_via_writing_graph",
        ) as mock_graph:

            async def fake_gen(*a: Any, **kw: Any) -> Any:
                yield StreamChunk(text="done", is_final=True)

            mock_graph.side_effect = lambda *a, **kw: fake_gen(a, kw)

            request = GenerationRequest(
                chapter_id=uuid4(),
                project_id=uuid4(),
                user_id=uuid4(),
                mode=GenerationMode.FULL_DRAFT,
            )

            config = MagicMock(spec=ResolvedModelConfig)
            chunks: list[Any] = []
            async for chunk in pipeline._full_draft(request, WritingContext(), config):
                chunks.append(chunk)

            mock_graph.assert_called_once()
            assert len(chunks) == 1
            assert chunks[0].text == "done"
