"""ChatAgent — a conversational agent for free-form chat.

Provides an ADR-024 compliant conversational agent that uses
``HistoryPolicy.CONVERSATIONAL`` to maintain process history across turns.

Usage:
    agent = ChatAgent(model=model)
    deps = ChatDeps(prompt_composer=composer, context=ctx, user_prompt=msg)

    # Streaming response
    async for event in agent.run_stream(prompt="", deps=deps):
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
    (auto-injected by ``NarrareAgent``). The actual per-request prompt
    composition uses ``PromptComposer`` cascade via ``ChatDeps``.

    The ``prompt`` parameter to ``run_stream()`` may be:
    - The composed user prompt (pre-composed via ``PromptComposer``)
    - An empty string when using ``PromptComposer`` via ``ChatDeps``
    """

    def __init__(
        self,
        model: Model,
    ) -> None:
        """Initialise the ChatAgent.

        Args:
            model: Pydantic-ai Model instance from ModelRegistry.
        """
        super().__init__(
            model=model,
            deps_type=ChatDeps,
            history_policy=HistoryPolicy.CONVERSATIONAL,
        )
