"""WebSocket dispatch for interview-assisted draft generation.

Bridges the transport-agnostic :class:`InterviewDraftGenerator` (which
yields :class:`StreamChunk`) with the WebSocket transport: maps chunks
to DTOs via :func:`send_stream_chunks`, handles errors, persists the
draft, and sends the completion message.

ADR-045 Decision 6: WebSocket-specific orchestration lives outside the
transport-agnostic generator and outside the message-routing handler,
keeping each module focused on one responsibility (RULE-04/RULE-06).

See: CONSTRAINTS.md RULE-04/RULE-06/RULE-12.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.writing.ws_streaming import StreamSender
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.writing.session_manager import SessionManager

logger = structlog.get_logger(__name__)


async def dispatch_interview_draft(
    *,
    websocket: StreamSender,
    session_id: UUID,
    user_id: UUID,
    project_id: UUID,
    chapter_id: UUID,
    session_manager: SessionManager,
    registry: ModelRegistry,
    composer: PromptComposer,
    config: ResolvedModelConfig,
    invocation_pipeline: InvocationPipeline | None,
    run_limit_resolver: DefaultRunLimitResolver,
    api_key: str | None = None,
    base_url: str | None = None,
) -> None:
    """Orchestrate interview draft generation over a WebSocket transport.

    Fetches the ownership-gated novel title/genre for the draft prompt
    (``resolve_draft_novel_context`` — WS short-lived-session precedent;
    RULE-11 degrade to empty), constructs the transport-agnostic
    :class:`InterviewDraftGenerator`, streams chunks to DTOs via
    :func:`send_stream_chunks`, persists the completed draft, and sends
    the ``draft_done`` message. Errors from the invocation contract or
    the LLM are mapped to ``error`` DTOs.

    Args:
        websocket: A :class:`StreamSender` (any object with an async
            ``send_json`` method, e.g. ``fastapi.WebSocket``).
        session_id: The WebSocket session identifier.
        user_id: The authenticated user's identifier (ADR-045).
        project_id: The project identifier for enrichment.
        chapter_id: The chapter being written.
        session_manager: Session state manager for transcript + prose.
        registry: Model registry for LLM streaming (RULE-01b).
        composer: Prompt composer for prompt assembly (RULE-02).
        config: Fully resolved model configuration.
        invocation_pipeline: Invocation pipeline for enrichment,
            validation, budget resolution, and evidence (ADR-045).
        run_limit_resolver: Resolves output budgets into runtime
            limits (ADR-045 Decision 4).
        api_key: Optional provider API key override.
        base_url: Optional provider base URL override.
    """
    from narrare.writing._interview_draft import InterviewDraftGenerator
    from narrare.writing._interview_draft_support import resolve_draft_novel_context
    from narrare.writing.ws_streaming import send_stream_chunks
    from narrare_core.shared.errors import WritingError

    project_title, genre = await resolve_draft_novel_context(
        user_id=user_id,
        project_id=project_id,
    )

    generator = InterviewDraftGenerator(
        session_manager=session_manager,
        registry=registry,
        composer=composer,
        config=config,
        invocation_pipeline=invocation_pipeline,
        run_limit_resolver=run_limit_resolver,
        api_key=api_key,
        base_url=base_url,
    )

    try:
        result = await send_stream_chunks(
            websocket,
            generator.stream_draft(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter_id,
                project_title=project_title,
                genre=genre,
            ),
        )
    except WritingError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        return
    except Exception as e:
        logger.error(
            "interview_draft_failed",
            session_id=str(session_id),
            error=str(e),
        )
        await websocket.send_json({"type": "error", "message": f"Draft generation failed: {e}"})
        return

    full_text = result.full_text
    if not full_text:
        return

    word_count = len(full_text.split())
    await session_manager.add_message(session_id, "assistant", full_text)
    await session_manager.append_prose(session_id, full_text)
    await websocket.send_json(
        {
            "type": "draft_done",
            "text": full_text,
            "word_count": word_count,
        }
    )
