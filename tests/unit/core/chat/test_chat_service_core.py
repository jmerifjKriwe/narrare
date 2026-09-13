"""Unit tests for ``narrare_core.chat.chat_service_core`` — pure builders.

Covers the parts of the chat context builder NOT pinned elsewhere:
- novel-metadata passthrough (FO-7 follow-up: the API seam threads the
  owned novel's title/genre into the builder params),
- history formatting,
- conversation-id generation.

The FO-7 slot supply (four explicitly-empty slots) is pinned at render
level in ``tests/unit/core/prompts/test_chat_prompt_render.py``
(TestChatSupplyFix) and at seam level in
``tests/unit/api/chat/test_chat_service_project_context.py``.
"""

from __future__ import annotations

from uuid import UUID

from narrare_core.chat.chat_service_core import (
    build_chat_context,
    format_history,
    new_conversation_id,
)
from narrare_core.chat.contracts import ChatMessage


class TestBuildChatContextNovelMetadata:
    """FO-7 follow-up: the builder carries novel metadata into PromptContext."""

    def test_build_chat_context_carries_novel_metadata(self) -> None:
        """Title/genre params land on the PromptContext fields the chat
        template renders into its Project Context section."""
        context = build_chat_context(
            project_title="The Ashen Court",
            genre="Dark Fantasy",
            language="en",
        )

        assert context.project_title == "The Ashen Court"
        assert context.genre == "Dark Fantasy"
        assert context.language == "en"

    def test_build_chat_context_defaults_are_project_less(self) -> None:
        """Default params keep the project-less minimal-tier shape."""
        context = build_chat_context(project_title="", genre="", language="en")

        assert context.project_title == ""
        assert context.genre == ""


class TestFormatHistory:
    """``format_history`` — Author/Assistant prefixes, bounded window."""

    @staticmethod
    def _message(role: str, content: str) -> ChatMessage:
        """Build a ChatMessage with throwaway ids (pure formatting input)."""
        from uuid import uuid4

        return ChatMessage(
            conversation_id=uuid4(),
            role=role,
            content=content,
            message_id=uuid4(),
        )

    def test_format_history_prefixes_roles(self) -> None:
        history = [
            self._message("user", "How do I pace my opening?"),
            self._message("assistant", "Start in motion."),
        ]
        rendered = format_history(history)

        assert rendered == "Author: How do I pace my opening?\n\nAssistant: Start in motion."

    def test_format_history_trims_to_max_messages(self) -> None:
        history = [self._message("user", f"msg-{i}") for i in range(60)]
        rendered = format_history(history, max_history_messages=50)

        assert "msg-9" not in rendered  # first 10 trimmed
        assert "msg-10" in rendered
        assert "msg-59" in rendered

    def test_format_history_empty_history_renders_empty(self) -> None:
        assert format_history([]) == ""


class TestNewConversationId:
    """``new_conversation_id`` — fresh UUIDv4 per call."""

    def test_new_conversation_id_returns_unique_uuids(self) -> None:
        first = new_conversation_id()
        second = new_conversation_id()

        assert isinstance(first, UUID)
        assert first != second
