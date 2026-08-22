"""Unit tests for InMemoryConversationStore — edge cases and auto-trim.

Tests the auto-trim behaviour when message count exceeds ``max_messages``
and conversation metadata resolution.

No I/O, no DB — pure in-memory store.
"""

from __future__ import annotations

from uuid import uuid4

from narrare_core.chat.conversation_store import InMemoryConversationStore

# ---------------------------------------------------------------------------
# Auto-trim
# ---------------------------------------------------------------------------


class TestAutoTrim:
    """Messages exceeding ``max_messages`` are automatically trimmed."""

    async def test_add_message_auto_trims_when_over_limit(self) -> None:
        """Adding more messages than max_messages keeps only the newest."""
        store = InMemoryConversationStore(max_messages=3)
        conv_id = uuid4()

        for i in range(5):
            await store.add_message(conv_id, "user", f"msg {i}")

        history = await store.get_history(conv_id)

        assert len(history) == 3
        assert history[0].content == "msg 2"
        assert history[1].content == "msg 3"
        assert history[2].content == "msg 4"

    async def test_add_message_no_trim_when_at_limit(self) -> None:
        """Messages at exactly max_messages are not trimmed."""
        store = InMemoryConversationStore(max_messages=5)
        conv_id = uuid4()

        for i in range(5):
            await store.add_message(conv_id, "user", f"msg {i}")

        history = await store.get_history(conv_id)

        assert len(history) == 5

    async def test_add_message_returns_created_message(self) -> None:
        """add_message returns a ChatMessage with the correct attributes."""
        store = InMemoryConversationStore()
        conv_id = uuid4()

        msg = await store.add_message(conv_id, "assistant", "Hello!")

        assert msg.conversation_id == conv_id
        assert msg.role == "assistant"
        assert msg.content == "Hello!"
        assert msg.created_at != ""


# ---------------------------------------------------------------------------
# get_conversation_project_id
# ---------------------------------------------------------------------------


class TestGetConversationProjectId:
    """Project ID resolution for conversations."""

    async def test_returns_project_id_for_known_conversation(self) -> None:
        """A conversation created via create_conversation resolves its project_id."""
        store = InMemoryConversationStore()
        project_id = uuid4()
        user_id = uuid4()

        conv_id = await store.create_conversation(project_id, user_id, "Hello")

        assert await store.get_conversation_project_id(conv_id) == project_id

    async def test_returns_none_for_unknown_conversation(self) -> None:
        """An unknown conversation_id returns None."""
        store = InMemoryConversationStore()

        assert await store.get_conversation_project_id(uuid4()) is None


# ---------------------------------------------------------------------------
# Project-less conversations (NOTES-001 §6b)
# ---------------------------------------------------------------------------


class TestProjectlessConversations:
    """create_conversation(None, ...) — behavioral contract for project-less chat."""

    async def test_create_conversation_without_project_works(self) -> None:
        """A project-less conversation is created, stored, and resolves project_id None."""
        store = InMemoryConversationStore()
        user_id = uuid4()

        conv_id = await store.create_conversation(None, user_id, "Global note chat")

        history = await store.get_history(conv_id)
        assert [m.content for m in history] == ["Global note chat"]
        assert await store.get_conversation_project_id(conv_id) is None


# ---------------------------------------------------------------------------
# clear_history
# ---------------------------------------------------------------------------


class TestClearHistory:
    """clear_history removes messages and conversation metadata."""

    async def test_clear_removes_messages_and_metadata(self) -> None:
        """Clearing removes both messages and conversation entry."""
        store = InMemoryConversationStore()
        project_id = uuid4()
        user_id = uuid4()

        conv_id = await store.create_conversation(project_id, user_id, "Hello")
        await store.add_message(conv_id, "assistant", "Hi!")

        await store.clear_history(conv_id)

        history = await store.get_history(conv_id)
        assert len(history) == 0
        assert await store.get_conversation_project_id(conv_id) is None

    async def test_clear_unknown_conversation_is_noop(self) -> None:
        """Clearing an unknown conversation does not raise."""
        store = InMemoryConversationStore()

        await store.clear_history(uuid4())
