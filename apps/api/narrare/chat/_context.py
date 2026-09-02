"""Chat prompt-context assembly (RULE-04 extraction from chat_service).

Owns the single responsibility of building the chat ``PromptContext``:
the core chat context (project metadata placeholders) plus the
conversation history rendered into ``extra["conversation_history"]``.

Extracted from ``chat_service.py`` for RULE-04 compliance — the service
was at the 300-line hard limit and the per-user credential threading
(Task 4 user-routing migration) pushed it over; modularise, never
compress.

See:
    narrare_core.chat.chat_service_core.build_chat_context (core builder),
    RULE-04 (Modularise, never compress).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.chat.chat_service_core import build_chat_context, format_history

if TYPE_CHECKING:
    from narrare_core.chat.contracts import ChatMessage
    from narrare_core.prompts.context import PromptContext


def build_prompt_context(history: list[ChatMessage]) -> PromptContext:
    """Build the chat PromptContext with the conversation history attached.

    Args:
        history: The conversation messages (oldest first) from the store.

    Returns:
        A PromptContext with ``extra["conversation_history"]`` populated.
    """
    context = build_chat_context(
        project_title="",
        genre="",
        language="en",
    )
    context.extra["conversation_history"] = format_history(history)
    return context
