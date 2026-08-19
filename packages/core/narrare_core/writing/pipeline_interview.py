"""Interview-assisted generation mode.

Split from pipeline.py to respect RULE-04 (file size limit).
Generates interview questions via LLM; the API layer collects answers
and calls the pipeline again in ``full_draft`` mode.

AUFG-03-01: the question round now runs through ``InterviewQuestionAgent``
(a ``NarrareAgent`` subtype) instead of calling ``ModelRegistry.run()``
directly. This guarantees the ADR-026 capabilities
(``NarrareMeta`` / ``NarrareUniversalRules`` / ``NarrareObservability``)
are injected, and routes through the ``AgentRegistry`` cache when wired.
The prompt is still composed upstream via ``_build_and_validate_prompt``
(Mode 1, ADR-048) so evidence/enrichment/limits continue to flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import structlog

from narrare_core.agents.interview_question_agent import (
    InterviewDeps,
    InterviewQuestionAgent,
)
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.result import StreamChunk
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import WritingError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.writing.models import GenerationRequest, WritingContext
    from narrare_core.writing.pipeline import WritingPipeline

logger = structlog.get_logger(__name__)


async def _get_or_create_interview_agent(
    pipeline: WritingPipeline,
    model: Any,
    system_prompt: str | None,
) -> InterviewQuestionAgent:
    """Resolve the interview agent via the registry when wired.

    Mirrors the ``get_or_create_agent`` pattern from
    ``agents/writing_graph_prompts.py``: if ``WritingPipeline`` has an
    ``AgentRegistry``, the agent is cached by ``(type, model, system_prompt)``
    (prompt-caching friendly, ADR-016 Phase 0); otherwise it is
    instantiated directly (test/standalone path).
    """
    registry = pipeline._agent_registry  # pyright: ignore[reportPrivateUsage]
    if registry is not None:
        # AgentRegistry.get_or_create is typed NarrareAgent[Any, Any] (it
        # serves every agent class); the requested agent_type parameterizes
        # the actual runtime type, so the cast narrows to the caller's view.
        return cast(
            "InterviewQuestionAgent",
            await registry.get_or_create(
                InterviewQuestionAgent,
                model,
                system_prompt=system_prompt,
            ),
        )
    return InterviewQuestionAgent(model=model, system_prompt=system_prompt)


async def stream_interview_assisted(
    pipeline: WritingPipeline,
    request: GenerationRequest,
    context: WritingContext,
    config: ResolvedModelConfig,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AsyncIterator[StreamChunk]:
    """Generate interview questions for the writer.

    The API layer handles the interactive interview loop and then
    calls the pipeline again with ``full_draft`` mode, using the
    collected answers as ``request.prompt``.
    """
    prompt_context = PromptContext(
        language=context.language,
        project_title=context.project_title,
        genre=context.genre,
        mode="interview",
        author_instructions=request.outline or request.prompt or "",
        extra={
            "user_id": str(request.user_id),
            "project_id": str(request.project_id),
            "chapter_outline": context.chapter_outline,
            "kb_characters": context.kb_characters,
            "recent_chapters": context.recent_chapters,
        },
    )
    # Keep prompt composition upstream so Mode 1 (ADR-048) evidence,
    # enrichment and limits continue to flow — the migration only
    # replaces the LLM-call boundary, not the prompt path.
    prompt = await pipeline._build_and_validate_prompt(  # pyright: ignore[reportPrivateUsage]
        LLMIntent.CHAT,
        prompt_context,
        user_id=request.user_id,
        project_id=request.project_id,
    )

    try:
        model = await pipeline._registry.get_model(  # pyright: ignore[reportPrivateUsage]
            config,
            api_key=api_key,
            base_url=base_url,
        )
        agent = await _get_or_create_interview_agent(
            pipeline,
            model=model,
            system_prompt=prompt.system or None,
        )
        deps = InterviewDeps(
            language=context.language,
            user_id=str(request.user_id),
            project_id=str(request.project_id),
        )
        result_text: str = await agent.run(prompt=prompt.user, deps=deps)
    except Exception as e:
        raise WritingError(
            f"Interview question generation failed: {e}",
            code="INTERVIEW_FAILED",
        ) from e

    yield StreamChunk(text=result_text)
    yield StreamChunk(text="", is_final=True, usage=None)
