"""ChatAgent — a conversational agent for free-form chat.

Provides an ADR-024 compliant conversational agent that uses
``HistoryPolicy.CONVERSATIONAL`` to maintain process history across turns.

ADR-046 (Prompt-Path-Compliance): the feature system prompt resolved by
``PromptComposer`` for ``LLMIntent.CHAT`` (``chat/{lang}/system.md``) is
injected into the **system channel** via the ``system_prompt`` constructor
parameter — it must NOT be concatenated into the user prompt. The
``NarrareMeta`` and ``NarrareUniversalRules`` capabilities continue to
supply the guaranteed identity/rules layer (ADR-026); the feature prompt is
an additional instructions layer.

Usage:
    # system_prompt comes from PromptComposer.build(LLMIntent.CHAT, ctx).system
    agent = ChatAgent(model=model, system_prompt=composed.system)
    deps = ChatDeps(prompt_composer=composer, context=ctx, user_prompt=msg)

    # Streaming response — prompt is the user-channel message only
    async for event in agent.run_stream(prompt=composed.user, deps=deps):
        if event.type == "token":
            # Stream partial text to client
            yield event.text
        elif event.type == "done":
            # Final response with usage info
            print(f"Done. Usage: {event.usage}")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.agents.base import NarrareAgent
from narrare_core.agents.history_policy import HistoryPolicy
from narrare_core.chat.chat_deps import ChatDeps

if TYPE_CHECKING:
    from pydantic_ai.models import Model


class ChatAgent(NarrareAgent[ChatDeps, str]):
    """Conversational agent for free-form chat.

    Uses ``HistoryPolicy.CONVERSATIONAL`` to maintain process history
    across turns.

    The agent's system prompt / built-in instructions are configured
    via the ``NarrareMeta`` and ``NarrareUniversalRules`` capabilities
    (auto-injected by ``NarrareAgent``). The per-request feature system
    prompt resolved by ``PromptComposer`` for ``LLMIntent.CHAT`` is injected
    into the system channel via the ``system_prompt`` constructor parameter
    (ADR-046) — this is an additional instructions layer on top of the
    guaranteed capabilities, NOT a replacement.

    The ``prompt`` parameter to ``run_stream()`` carries only the
    user-channel message (the composed user prompt or raw user message).
    """

    def __init__(
        self,
        model: Model,
        *,
        system_prompt: str | None = None,
    ) -> None:
        """Initialise the ChatAgent.

        Args:
            model: Pydantic-ai Model instance from ModelRegistry.
            system_prompt: The feature system prompt for ``LLMIntent.CHAT``
                as resolved by ``PromptComposer.build(LLMIntent.CHAT, ctx).system``
                (``chat/{lang}/system.md``). Injected into the **system
                channel** (ADR-046). ``None`` omits the feature system prompt
                — the guaranteed ``NarrareMeta``/``NarrareUniversalRules``
                capabilities are always present regardless.
        """
        super().__init__(
            model=model,
            deps_type=ChatDeps,
            system_prompt=system_prompt,
            history_policy=HistoryPolicy.CONVERSATIONAL,
        )
