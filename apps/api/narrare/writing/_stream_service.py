"""Writing generation stream loop (RULE-04 extraction from service).

Owns the iteration step of the generation flow: drives
``WritingPipeline.generate``, accumulates streamed text, finalizes the
request row on the final chunk (word count + best-effort session
memory), and degrades a failed stream to a ``failed`` status row.

Extracted from ``WritingService.stream_generation`` per RULE-04
(300-line service limit), following the ``chat._agent_stream`` split
precedent.  One responsibility (RULE-06): stream one generation to
completion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.writing.models import GenerationRequest
    from narrare.writing.repository import GenerationRepository
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.result import StreamChunk
    from narrare_core.memory.protocols import SessionMemoryCollector
    from narrare_core.writing._enums import GenerationMode
    from narrare_core.writing.draft_processor import DraftProcessor
    from narrare_core.writing.models import GenerationRequest as CoreGenerationRequest
    from narrare_core.writing.pipeline import WritingPipeline

from narrare.writing._helpers import record_session_memory

logger = structlog.get_logger(__name__)


async def stream_pipeline_chunks(
    *,
    repo: GenerationRepository,
    pipeline: WritingPipeline,
    draft_processor: DraftProcessor,
    session_memory: SessionMemoryCollector | None,
    request_model: GenerationRequest,
    request_id: UUID,
    mode: GenerationMode,
    pipeline_request: CoreGenerationRequest,
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
    custom_tone_instructions: str | None,
    kb_relationships: str,
    cross_session_context: str,
    series_history: str,
    project_title: str,
    genre: str,
    context_kwargs: dict[str, Any],
) -> AsyncIterator[StreamChunk]:
    """Stream generated text chunks and finalize the request row.

    Pure move of the ``WritingService.stream_generation`` iteration
    block: on the final chunk the accumulated text is cleaned, the word
    count persisted, and the writing session recorded (best-effort).
    Any stream failure marks the request ``failed`` with a partial word
    count (RULE-11: logged, never silent).

    Args:
        repo: Generation repository for status persistence.
        pipeline: The writing pipeline driving the LLM stream.
        draft_processor: Post-processor for cleaned text extraction.
        session_memory: Optional mem0 collector (no-op when None).
        request_model: The persisted generation request.
        request_id: The generation request ID (status updates).
        mode: The resolved generation mode enum.
        pipeline_request: Core request built from the ORM model.
        config: Resolved model configuration for the LLM call.
        api_key: Optional API key override.
        base_url: Optional base URL override.
        custom_tone_instructions: Resolved custom-tone block.
        kb_relationships: Formatted KB relationship text.
        cross_session_context: Cross-session mem0 context block.
        series_history: Series-history block (ADR-082).
        project_title: Ownership-checked novel title supply ("" degraded).
        genre: Ownership-checked novel genre supply ("" degraded).
        context_kwargs: Router-supplied pipeline overrides.

    Yields:
        Stream chunks from the pipeline, in order.
    """
    accumulated: list[str] = []
    try:
        async for chunk in pipeline.generate(
            pipeline_request,
            config=config,
            api_key=api_key,
            base_url=base_url,
            custom_tone_instructions=custom_tone_instructions,
            kb_relationships=kb_relationships,
            cross_session_context=cross_session_context,
            series_history=series_history,
            project_title=project_title,
            genre=genre,
            **context_kwargs,
        ):
            if chunk.is_final:
                raw_text = "".join(accumulated) + chunk.text
                cleaned = draft_processor.process(raw_text)
                word_count = len(cleaned.split())
                await repo.update_status(
                    request_id,
                    "completed",
                    tokens_used=chunk.usage.total_tokens if chunk.usage else 0,
                    word_count=word_count,
                    completed_at=datetime.now(UTC),
                )
                # Record writing session to mem0 (best-effort)
                await record_session_memory(
                    session_memory,
                    request_model,
                    mode.value,
                    word_count,
                )
                yield chunk
                return
            accumulated.append(chunk.text)
            yield chunk
    except Exception as e:
        partial = draft_processor.process("".join(accumulated), is_partial=True)
        partial_words = len(partial.split()) if partial else 0
        await repo.update_status(
            request_id,
            "failed",
            error_message=str(e),
            word_count=partial_words,
            completed_at=datetime.now(UTC),
        )
        logger.error("generation_stream_failed", request_id=str(request_id), error=str(e))
