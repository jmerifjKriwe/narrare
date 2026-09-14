"""WritingGraph integration for the writing pipeline.

Provides paths that delegate full-draft generation
to the pydantic-graph based WritingGraph workflow.
Supports optional state persistence for interrupted graph runs.

Extracted from pipeline.py per RULE-04 (file size limits).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare_core.llm.result import StreamChunk

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.agents.graph_store import GraphStateStore
    from narrare_core.agents.registry import AgentRegistry
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.models import GenerationRequest, WritingContext

logger = structlog.get_logger(__name__)


async def stream_via_writing_graph(
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    registry: object,
    composer: PromptComposer,
    context_assembler: object,
    agent_registry: AgentRegistry | None = None,
    invocation_pipeline: InvocationPipeline | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """Generate via WritingGraph (pydantic-graph based workflow).

    The graph runs plan → draft → review → finalize internally.
    It returns the completed text as a single chunk (no streaming).
    """
    from narrare_core.agents.writing_graph_types import (
        WritingDeps,
        WritingState,
        create_writing_graph,
    )

    graph = create_writing_graph()

    deps = WritingDeps(
        registry=registry,
        composer=composer,
        agent_registry=agent_registry,
        context_assembler=context_assembler,
        model_config=config,
        api_key=api_key,
        base_url=base_url,
        chapter_content=context.chapter_content,
        chapter_outline=context.chapter_outline,
        genre=context.genre,
        project_title=context.project_title,
        word_target=request.word_target,
        tone=context.tone,
        language=request.writing_language,
        writing_language=context.writing_language,
        user_id=str(request.user_id),
        invocation_pipeline=invocation_pipeline,
    )

    state = WritingState(
        chapter_id=str(request.chapter_id),
        novel_id=str(request.project_id),
    )

    result = await graph.run(state=state, deps=deps)
    # graph.run() returns OutputT (= WritingState) directly
    final_text = result.final
    yield StreamChunk(text=final_text, is_final=True, usage=None)


async def run_with_persistence(
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    registry: object,
    composer: PromptComposer,
    context_assembler: object,
    agent_registry: AgentRegistry | None = None,
    invocation_pipeline: InvocationPipeline | None = None,
    store: GraphStateStore | None = None,
    run_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """Generate via WritingGraph with optional state persistence.

    If a ``run_id`` is provided and a stored state exists, the graph
    resumes from that checkpoint. Otherwise a new run is started.

    After successful completion the store entry is cleaned up.
    """
    from narrare_core.agents.writing_graph_types import (
        WritingDeps,
        WritingState,
        create_writing_graph,
    )

    graph = create_writing_graph()

    # Resolve run_id
    current_run_id = run_id or str(uuid.uuid4())

    # Load previous state if available
    initial_state = WritingState(
        chapter_id=str(request.chapter_id),
        novel_id=str(request.project_id),
    )
    if store is not None and run_id is not None:
        saved = await store.load(run_id)
        if saved is not None and isinstance(saved, WritingState):
            initial_state = saved

    deps = WritingDeps(
        registry=registry,
        composer=composer,
        agent_registry=agent_registry,
        context_assembler=context_assembler,
        model_config=config,
        api_key=api_key,
        base_url=base_url,
        chapter_content=context.chapter_content,
        chapter_outline=context.chapter_outline,
        genre=context.genre,
        project_title=context.project_title,
        word_target=request.word_target,
        tone=context.tone,
        language=request.writing_language,
        writing_language=context.writing_language,
        store=store,
        run_id=current_run_id,
        user_id=str(request.user_id),
        invocation_pipeline=invocation_pipeline,
    )

    result = await graph.run(state=initial_state, deps=deps)

    # Save final state
    if store is not None:
        await store.save(current_run_id, result)

    final_text = result.final
    yield StreamChunk(text=final_text, is_final=True, usage=None)
