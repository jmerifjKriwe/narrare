"""WritingGraph integration for the writing pipeline.

Provides a feature-flagged path that delegates full-draft generation
to the pydantic-graph based WritingGraph workflow.

Extracted from pipeline.py per RULE-04 (file size limits).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.result import StreamChunk

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm.intents import ResolvedModelConfig
    from narrare_core.writing.models import GenerationRequest, WritingContext

logger = structlog.get_logger(__name__)


async def stream_via_writing_graph(
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    registry: object,
    context_assembler: object,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """Generate via WritingGraph (pydantic-graph based workflow).

    The graph runs plan → draft → review → finalize internally.
    It returns the completed text as a single chunk (no streaming).
    """
    from narrare_core.agents.writing_graph import create_writing_graph
    from narrare_core.agents.writing_graph_types import WritingDeps, WritingState

    graph = create_writing_graph()

    deps = WritingDeps(
        registry=registry,
        context_assembler=context_assembler,
        model_config=config,
        api_key=api_key,
        base_url=base_url,
        chapter_content=context.chapter_content,
        chapter_outline=context.chapter_outline,
        genre=context.genre,
        word_target=request.word_target,
        tone=context.tone,
        language=request.language,
    )

    state = WritingState(
        chapter_id=str(request.chapter_id),
        novel_id=str(request.project_id),
    )

    result = await graph.run(state=state, deps=deps)
    # result.data is WritingState (see create_writing_graph docstring)
    final_text = result.data.final
    yield StreamChunk(text=final_text, is_final=True, usage=None)
