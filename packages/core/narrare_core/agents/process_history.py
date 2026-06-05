"""Process history for conversational agents (ADR-034).

When HistoryPolicy is CONVERSATIONAL, the agent accumulates message
history across turns. ``ProcessHistory`` is a lightweight container
that stores pydantic-ai message lists for conversational continuity.

Usage:
    history = ProcessHistory()

    # First turn — no prior history
    async for event in agent.run_stream(prompt, deps):
        if event.type == "done" and event.new_messages:
            history.add(event.new_messages)

    # Second turn — continuation
    async for event in agent.run_stream(prompt, deps, message_history=history.messages):
        if event.type == "done" and event.new_messages:
            history.add(event.new_messages)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProcessHistory:
    """Stores message history for conversational agents.

    When ``HistoryPolicy`` is ``CONVERSATIONAL``, the agent accumulates
    message history across turns. This class manages that history.

    Usage:
        history = ProcessHistory()
        async for event in agent.run_stream(prompt, deps, message_history=history.messages):
            if event.type == "done" and event.new_messages:
                history.add(event.new_messages)
    """

    messages: list[Any] = field(default_factory=list)  # pyright: ignore[reportUnknownVariableType] — pydantic-ai ModelMessage is opaque here

    def add(self, new_messages: list[Any]) -> None:
        """Append new messages to the history.

        Args:
            new_messages: Messages from ``StreamEvent.new_messages``
                (``result.new_messages()`` from pydantic-ai).
        """
        self.messages.extend(new_messages)

    def clear(self) -> None:
        """Clear all stored history."""
        self.messages.clear()

    @property
    def is_empty(self) -> bool:
        """Whether history contains no messages.

        Returns:
            True if no messages are stored, False otherwise.
        """
        return len(self.messages) == 0
