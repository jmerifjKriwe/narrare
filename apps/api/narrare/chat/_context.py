"""Chat context preparation (NOTES-001 §6b aware).

Owns the context steps of the chat flow:
- :func:`assemble_chat_context` builds the base ``PromptContext`` and folds
  the formatted conversation history into it (ADR-024 minimal tier).
- :func:`compose_chat_prompt` composes the chat prompt via the
  PromptComposer cascade (RULE-02 — never inline in the service).
- :func:`prepare_effective_context` composes the ADR-048 Mode 2 invocation
  and returns the enriched context that flows to ``ChatDeps`` — skipping
  project-correlated enrichment for project-less conversations (NOTES-001
  §6b: without a project there is nothing to correlate; graceful skip with
  a log, no error — RULE-11).
- :func:`resolve_effective_message` resolves the effective user message,
  prepending a requested scratchpad note as a runtime context block
  (NOTES-001 §6b — user-message channel, never a prompt template,
  RULE-02; graceful degradation on missing/unowned notes, RULE-11).

Extracted from ``chat_service.py`` for RULE-04 (300-line service limit),
following the ``_invocation.py`` / ``_response_helpers.py`` split pattern.
One responsibility (RULE-06): prepare the effective chat context.

See: ADR-024, ADR-045, ADR-048, NOTES-001 §6b,
CONSTRAINTS.md RULE-02/RULE-04/RULE-06/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.chat.chat_service_core import build_chat_context, format_history
from narrare_core.notes.contracts import format_note_context_block

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.chat.contracts import ChatMessage
    from narrare_core.notes.contracts import NoteLookupProtocol, NoteSnapshot
    from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
    from narrare_core.prompts.context import PromptContext

logger = structlog.get_logger(__name__)


def assemble_chat_context(history: list[ChatMessage]) -> PromptContext:
    """Build the base chat ``PromptContext`` with formatted history.

    Args:
        history: Prior messages of the conversation (empty when new).

    Returns:
        The minimal ADR-024 context with ``conversation_history`` in
        ``extra``.
    """
    context = build_chat_context(
        project_title="",
        genre="",
        language="en",
    )
    context.extra["conversation_history"] = format_history(history)
    return context


async def compose_chat_prompt(
    composer: PromptComposer,
    context: PromptContext,
    user_prompt: str,
) -> ComposedPrompt:
    """Compose the chat prompt (system + user) via the PromptComposer cascade.

    Args:
        composer: The PromptComposer — prompts are built exclusively here
            (RULE-02), never inline in the service.
        context: The assembled chat context.
        user_prompt: The raw user message text.

    Returns:
        The composed prompt for ``LLMIntent.CHAT``.
    """
    from narrare_core.llm.intents import LLMIntent

    return await composer.build(LLMIntent.CHAT, context, user_prompt=user_prompt)


async def prepare_effective_context(
    *,
    invocation_pipeline: InvocationPipeline | None,
    prompt_ctx: PromptContext,
    user_id: UUID,
    project_id: UUID | None,
    conv_id: UUID,
    invocation_id: UUID,
) -> PromptContext:
    """Return the context for ``ChatDeps``, skipping enrichment when project-less.

    Runs ``compose_chat_invocation()`` (ADR-048 Mode 2) for correlated
    evidence + enrichment. NOTES-001 §6b: without a project there is
    nothing to correlate — pass no pipeline so ``compose_chat_invocation``
    takes its documented no-op path (backward compatible). The skip is
    logged, not raised (RULE-11: graceful degradation, no error).

    Args:
        invocation_pipeline: The InvocationPipeline, or ``None`` for a no-op.
        prompt_ctx: The original chat prompt context.
        user_id: The authenticated user's UUID (ADR-045 Decision 6).
        project_id: The project UUID for enrichment correlation, or
            ``None`` for project-less chat (NOTES-001 §6b).
        conv_id: The conversation UUID.
        invocation_id: The per-turn invocation UUID.

    Returns:
        The enriched ``PromptContext`` (or the original on failure / no-op).
    """
    from narrare.chat._invocation import compose_chat_invocation

    if project_id is None:
        logger.info(
            "chat_project_context_skipped",
            conversation_id=str(conv_id),
        )
    return await compose_chat_invocation(
        invocation_pipeline=invocation_pipeline if project_id is not None else None,
        prompt_ctx=prompt_ctx,
        user_id=user_id,
        project_id=project_id,
        conv_id=conv_id,
        invocation_id=invocation_id,
    )


async def resolve_effective_message(
    *,
    note_lookup: NoteLookupProtocol | None,
    note_id: UUID | None,
    message: str,
    user_id: UUID,
) -> str:
    """Resolve the effective user message with an optional note attached.

    NOTES-001 §6b: when the request carries a ``note_id``, the note snapshot
    is serialized via ``format_note_context_block`` (core contract) and
    prepended to the user message — RUNTIME INPUT in the user-message
    channel, never baked into a system/task template (RULE-02; same
    category as ``format_history``). A missing/unowned note (snapshot is
    ``None``) or an unwired lookup degrades gracefully: warn and proceed
    without the note (RULE-11 — no error mid-conversation).

    Args:
        note_lookup: ``NoteLookupProtocol`` implementation (the notes
            service, injected by wiring), or ``None`` when note injection
            is not wired.
        note_id: The note to attach, or ``None`` for plain chat (no
            lookup is performed then).
        message: The raw user message text.
        user_id: The authenticated user's UUID (ownership check).

    Returns:
        The effective message — ``"<note block>\\n\\n<message>"`` when a
        note was found, otherwise the original message unchanged.
    """
    if note_id is None:
        return message

    snapshot: NoteSnapshot | None = None
    if note_lookup is not None:
        snapshot = await note_lookup.get_note_snapshot(note_id, user_id)

    if snapshot is None:
        logger.warning(
            "chat_note_unavailable",
            note_id=str(note_id),
        )
        return message

    return f"{format_note_context_block(snapshot)}\n\n{message}"
