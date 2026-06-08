"""Core business logic for free-form chat — pure functions, no I/O.

ADR-024: Minimal context tier (~700 tokens total).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from narrare_core.prompts.context import PromptContext

if TYPE_CHECKING:
    from narrare_core.chat.contracts import ChatMessage


def build_chat_context(
    project_title: str,
    genre: str,
    language: str,
    kb_characters: str = "",
    kb_locations: str = "",
    kb_factions: str = "",
    kb_relationships: str = "",
    recent_chapters: str = "",
) -> PromptContext:
    """Build a minimal PromptContext for chat (Tiers 1-4).

    ~700 tokens: project metadata + abbreviated KB summaries.
    No full entity details — just names and key facts.
    """
    context = PromptContext(
        language=language,
        project_title=project_title,
        genre=genre,
    )

    context.extra["kb_characters"] = kb_characters
    context.extra["kb_locations"] = kb_locations
    context.extra["kb_factions"] = kb_factions
    context.extra["kb_relationships"] = kb_relationships
    context.extra["recent_chapters"] = recent_chapters

    return context


def format_history(
    history: list[ChatMessage],
    *,
    max_history_messages: int = 50,
) -> str:
    """Format conversation history for prompt injection.

    Includes the last *max_history_messages* messages.
    """
    trimmed = history[-max_history_messages:]
    parts: list[str] = []
    for msg in trimmed:
        prefix = "Author" if msg.role == "user" else "Assistant"
        parts.append(f"{prefix}: {msg.content}")
    return "\n\n".join(parts)


def new_conversation_id() -> UUID:
    """Generate a new conversation ID."""
    return uuid4()
