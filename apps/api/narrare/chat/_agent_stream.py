"""Chat turn streaming orchestration (RULE-04 extraction from chat_service).

Owns the streaming step of the chat flow: resolves the model via the
single assembly point (``ModelRegistry.prepare`` with the routing
cascade's per-user credentials), composes the effective context
(ADR-048 Mode 2 — enrichment), creates the ``ChatAgent`` (ADR-046
system-channel injection), and delegates SSE mapping + persistence to
``chat._sse_stream``.

Extracted from ``chat_service.py`` for RULE-04 (300-line service
limit), following the ``_context.py`` / ``_invocation.py`` /
``_sse_stream.py`` split pattern. One responsibility (RULE-06): stream
one chat turn.

See: ADR-024, ADR-034, ADR-045, ADR-046, ADR-048, NOTES-001 §6b,
CONSTRAINTS.md RULE-04/RULE-06/RULE-11/RULE-13.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any
    from uuid import UUID

    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ModelRegistry, ResolvedModel, ResolvedModelConfig
    from narrare_core.llm._prepared_call import PreparedModelCall
    from narrare_core.llm.run_limits import DefaultRunLimitResolver
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
    from narrare_core.prompts.context import PromptContext

from narrare_core.agents.process_history import ProcessHistory
from narrare_core.llm.intents import LLMIntent


async def stream_agent_response(
    *,
    registry: ModelRegistry,
    config: ResolvedModelConfig,
    api_key: str | None,
    base_url: str | None,
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
    escalation: ResolvedModel | None = None,
) -> AsyncIterator[dict[str, object]]:
    """Stream one chat turn via ``ChatAgent.run_stream()`` (ADR-024).

    Resolves the model via the single assembly point (Task 6d — Task 4/5
    pattern): model + intent-aware runtime settings + usage limits as one
    coherent triple. ``api_key``/``base_url`` carry the resolved per-user
    credentials (model-routing cascade) into the resolution point; usage
    limits stay owned by the ADR-045 run-limit resolver.

    Composes the ADR-048 Mode 2 invocation next for evidence + enrichment
    (flows to ``ChatDeps``); a no-op when ``invocation_pipeline`` is
    ``None`` (backward compatible). Project-less conversations skip
    project-correlated enrichment inside ``prepare_effective_context``
    (NOTES-001 §6b — graceful, logged). See ``chat._context`` and
    ``chat._invocation`` for details.

    Args:
        registry: For LLM model resolution (single assembly point).
        config: Resolved model configuration (provider, model, params).
        api_key: Resolved per-user credential (model-routing cascade).
        base_url: Resolved base-URL override, or ``None`` for the default.
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
        project_id: The project UUID for enrichment correlation, or
            ``None`` for project-less chat (NOTES-001 §6b).
        escalation: Optional resolved escalation (ANALYSE) triple
            (ADR-089) — ``None`` unless the pilot flag was on at DI time,
            so the default-off path stays byte-identical to the
            pre-ADR-089 wiring.

    Yields:
        Dict-based SSE events for the streaming response.
    """
    from narrare.chat._context import prepare_effective_context
    from narrare.chat._invocation import resolve_chat_run_limits
    from narrare.chat._sse_stream import stream_agent_events as map_agent_events
    from narrare_core.chat.chat_agent import ChatAgent
    from narrare_core.chat.chat_deps import ChatDeps

    # Resolve the model via the single assembly point (Task 6d).
    prepared: PreparedModelCall = await registry.prepare(
        config,
        intent=LLMIntent.CHAT,
        api_key=api_key,
        base_url=base_url,
    )

    # Compose the invocation (Mode 2) → enriched context for ChatDeps.
    invocation_id = uuid4()
    effective_context = await prepare_effective_context(
        invocation_pipeline=invocation_pipeline,
        prompt_ctx=context,
        user_id=user_id,
        project_id=project_id,
        conv_id=conv_id,
        invocation_id=invocation_id,
    )

    # ADR-089 Decision 7: flag-gated tier-escalation capability build —
    # delegated to chat._tiering (RULE-04); ``escalation`` is None unless
    # the pilot flag was on at DI time (default-off → no behavior change).
    capabilities: list[Any] | None = None
    if escalation is not None:
        from narrare.chat._tiering import build_tier_capabilities

        capabilities = await build_tier_capabilities(registry, prepared.model, config, escalation)

    # Create ChatAgent (HistoryPolicy.CONVERSATIONAL). ADR-046: inject the
    # feature system prompt into the SYSTEM channel via the constructor,
    # never concatenated into the user prompt. ADR-089: the SelectModel
    # capability rides ``capabilities=``; the base model stays the
    # constructor model (upstream ``model_is_explicit`` authoritative).
    agent = ChatAgent(
        model=prepared.model,
        system_prompt=composed.system or None,
        capabilities=capabilities,
    )

    # ChatDeps carries the enriched context to the agent (ADR-048 Mode 2).
    deps = ChatDeps(
        prompt_composer=composer,
        context=effective_context,
        user_prompt=user_prompt,
    )

    # Get or create ProcessHistory for this conversation
    history = histories.get(conv_id, ProcessHistory())

    # Resolve run limits when a resolver is wired (ADR-045 Decision 4).
    # The assembly point's settings form the merge base; the resolver's
    # per-turn output cap stays authoritative on conflicts (Task 6d-1).
    message_history = history.messages if not history.is_empty else None
    stream_kwargs = resolve_chat_run_limits(
        resolver=run_limit_resolver,
        config=config,
        invocation_id=invocation_id,
        base_model_settings=prepared.model_settings,
    )

    # Map the agent stream to chat SSE events (ADR-024/ADR-034) and
    # persist the response — delegated to the RULE-04 bridge helper.
    async for event in map_agent_events(
        agent=agent,
        deps=deps,
        prompt=composed.user,
        message_history=message_history,
        stream_kwargs=stream_kwargs,
        conv_id=conv_id,
        history=history,
        histories=histories,
        store=store,
    ):
        yield event
