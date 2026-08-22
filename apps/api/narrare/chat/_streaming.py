"""Chat response streaming via ChatAgent (ADR-024 / ADR-048 Mode 2).

Owns the streaming step of the chat flow: resolves the model from the
registry, composes the effective context (ADR-048 Mode 2 — enrichment),
creates the ``ChatAgent`` (ADR-046 system-channel injection), and yields
SSE events while tracking ``ProcessHistory`` and persisting the assistant
response.

Extracted verbatim from ``chat_service.py`` for RULE-04 (300-line service
limit), following the ``_context.py`` / ``_invocation.py`` /
``_response_helpers.py`` split pattern. One responsibility (RULE-06):
stream one chat turn.

See: ADR-024, ADR-034, ADR-045, ADR-046, ADR-048, NOTES-001 §6b,
CONSTRAINTS.md RULE-04/RULE-06/RULE-11/RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from narrare_core.agents.process_history import ProcessHistory

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)


async def stream_chat_response(
    *,
    registry: ModelRegistry,
    config: ResolvedModelConfig,
    composer: PromptComposer,
    store: SQLAlchemyConversationStore,
    histories: dict[UUID, ProcessHistory],
    invocation_pipeline: InvocationPipeline | None,
    run_limit_resolver: DefaultRunLimitResolver | None,
    conv_id: UUID,
    composed: ComposedPrompt,
    context: PromptContext,
    user_prompt: str,
    user_id: UUID,
    project_id: UUID | None,
) -> AsyncIterator[dict[str, object]]:
    """Stream one chat turn via ``ChatAgent.run_stream()`` (ADR-024).

    Composes the ADR-048 Mode 2 invocation first for evidence + enrichment
    (flows to ``ChatDeps``); a no-op when ``invocation_pipeline`` is
    ``None`` (backward compatible). See ``chat._context`` and
    ``chat._invocation`` for details.

    Args:
        registry: For LLM model resolution.
        config: Resolved model configuration (provider, model, params).
        composer: For agent-internal prompt assembly (``ChatDeps``).
        store: For persisting the assistant response.
        histories: Shared per-conversation ``ProcessHistory`` map
            (ADR-034); this turn's messages are recorded in place.
        invocation_pipeline: Optional pipeline for chat-invocation evidence
            and enrichment (ADR-045/ADR-048); ``None`` is a no-op.
        run_limit_resolver: Optional run-limit resolver (ADR-045 Decision 4);
            ``None`` applies no limits to the stream.
        conv_id: The conversation UUID.
        composed: The composed prompt (system + user prompts).
        context: The prompt context with project metadata.
        user_prompt: The effective user message text (NOTES-001 §6b:
            may carry a note context block as runtime input).
        user_id: The authenticated user's UUID (ADR-045 Decision 6).
        project_id: The project UUID, or ``None`` for project-less
            conversations — invocation enrichment is skipped then
            (NOTES-001 §6b).

    Yields:
        Dict-based SSE events for the streaming response.
    """
    from narrare.chat._context import prepare_effective_context
    from narrare.chat._invocation import resolve_chat_run_limits
    from narrare.chat._response_helpers import save_assistant_response
    from narrare_core.chat.chat_agent import ChatAgent
    from narrare_core.chat.chat_deps import ChatDeps

    # Get model from registry
    model = await registry.get_model(config)

    # Compose the invocation (Mode 2) → enriched context for ChatDeps.
    # NOTES-001 §6b: project-less conversations skip project-correlated
    # enrichment inside prepare_effective_context (graceful, logged).
    invocation_id = uuid4()
    effective_context = await prepare_effective_context(
        invocation_pipeline=invocation_pipeline,
        prompt_ctx=context,
        user_id=user_id,
        project_id=project_id,
        conv_id=conv_id,
        invocation_id=invocation_id,
    )

    # Create ChatAgent (HistoryPolicy.CONVERSATIONAL). ADR-046: inject the
    # feature system prompt into the SYSTEM channel via the constructor,
    # never concatenated into the user prompt.
    agent = ChatAgent(model=model, system_prompt=composed.system or None)

    # ChatDeps carries the enriched context to the agent (ADR-048 Mode 2).
    deps = ChatDeps(
        prompt_composer=composer,
        context=effective_context,
        user_prompt=user_prompt,
    )

    # Get or create ProcessHistory for this conversation
    history = histories.get(conv_id, ProcessHistory())

    # Resolve run limits when a resolver is wired (ADR-045 Decision 4).
    message_history = history.messages if not history.is_empty else None
    stream_kwargs = resolve_chat_run_limits(
        resolver=run_limit_resolver,
        config=config,
        invocation_id=invocation_id,
    )

    # Yield meta event with conversation ID
    yield {
        "type": "meta",
        "conversation_id": str(conv_id),
        "request_id": str(uuid4()),
    }

    # Stream agent response. ADR-046: only composed.user (user channel) is
    # passed as prompt; the system prompt is injected via the constructor.
    full_response = ""
    try:
        async for event in agent.run_stream(
            prompt=composed.user,
            deps=deps,
            message_history=message_history,
            **stream_kwargs,
        ):
            if event.type == "token":
                yield {"type": "token", "text": event.text}
                full_response += event.text
            elif event.type == "done":
                # Update ProcessHistory with new messages from this turn
                if event.new_messages:
                    history.add(event.new_messages)
                    histories[conv_id] = history

                yield {
                    "type": "done",
                    "usage": event.usage or {},
                }
                # Use the complete text from the done event
                if event.text:
                    full_response = event.text
    except Exception as exc:
        logger.error(
            "chat_stream_failed",
            conversation_id=str(conv_id),
            error=str(exc),
            exc_info=True,
        )
        await save_assistant_response(store, conv_id, full_response)
        raise

    await save_assistant_response(store, conv_id, full_response)
