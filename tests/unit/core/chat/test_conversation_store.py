"""Unit tests for InMemoryConversationStore — edge cases and auto-trim.

Tests the auto-trim behaviour when message count exceeds ``max_messages``
and conversation metadata resolution.

No I/O, no DB — pure in-memory store.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare_core.chat.conversation_store import InMemoryConversationStore
from narrare_core.shared.errors import NotFoundError

# ---------------------------------------------------------------------------
# Auto-trim
# ---------------------------------------------------------------------------


class TestAutoTrim:
    """Messages exceeding ``max_messages`` are automatically trimmed."""

    async def test_add_message_auto_trims_when_over_limit(self) -> None:
        """Adding more messages than max_messages keeps only the newest."""
        store = InMemoryConversationStore(max_messages=3)
        user_id = uuid4()
        conv_id = await store.create_conversation(None, user_id, "seed")

        for i in range(5):
            await store.add_message(conv_id, "user", f"msg {i}")

        history = await store.get_history(conv_id, user_id)

        # Seed message + msg 0/1 were trimmed away; the newest 3 remain.
        assert len(history) == 3
        assert history[0].content == "msg 2"
        assert history[1].content == "msg 3"
        assert history[2].content == "msg 4"

    async def test_add_message_no_trim_when_at_limit(self) -> None:
        """Messages at exactly max_messages are not trimmed."""
        store = InMemoryConversationStore(max_messages=5)
        user_id = uuid4()
        conv_id = await store.create_conversation(None, user_id, "seed")

        for i in range(4):
            await store.add_message(conv_id, "user", f"msg {i}")

        history = await store.get_history(conv_id, user_id)

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
    """Project ID resolution for conversations (ownership-scoped)."""

    async def test_returns_project_id_for_known_conversation(self) -> None:
        """A conversation created via create_conversation resolves its project_id."""
        store = InMemoryConversationStore()
        project_id = uuid4()
        user_id = uuid4()

        conv_id = await store.create_conversation(project_id, user_id, "Hello")

        assert await store.get_conversation_project_id(conv_id, user_id) == project_id

    async def test_raises_not_found_for_unknown_conversation(self) -> None:
        """An unknown conversation_id raises NotFoundError (HTTP 404)."""
        store = InMemoryConversationStore()

        with pytest.raises(NotFoundError):
            await store.get_conversation_project_id(uuid4(), uuid4())


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

        history = await store.get_history(conv_id, user_id)
        assert [m.content for m in history] == ["Global note chat"]
        assert await store.get_conversation_project_id(conv_id, user_id) is None


# ---------------------------------------------------------------------------
# clear_history
# ---------------------------------------------------------------------------


class TestClearHistory:
    """clear_history removes messages; the conversation itself persists."""

    async def test_clear_removes_messages_but_keeps_conversation(self) -> None:
        """Clearing removes the messages; the owner can still read (empty)."""
        store = InMemoryConversationStore()
        project_id = uuid4()
        user_id = uuid4()

        conv_id = await store.create_conversation(project_id, user_id, "Hello")
        await store.add_message(conv_id, "assistant", "Hi!")

        await store.clear_history(conv_id, user_id)

        history = await store.get_history(conv_id, user_id)
        assert len(history) == 0
        # The conversation row persists (mirrors the SQLAlchemy store, where
        # only chat_messages rows are deleted) — project stays resolvable.
        assert await store.get_conversation_project_id(conv_id, user_id) == project_id

    async def test_clear_unknown_conversation_raises_not_found(self) -> None:
        """Clearing an unknown conversation raises NotFoundError (HTTP 404)."""
        store = InMemoryConversationStore()

        with pytest.raises(NotFoundError):
            await store.clear_history(uuid4(), uuid4())


# ---------------------------------------------------------------------------
# Ownership enforcement (IDOR hardening)
# ---------------------------------------------------------------------------


class TestGetConversation:
    """Scoped conversation resolution — the pre-write ownership gate.

    ``get_conversation`` powers the ownership check in ``ChatService.ask()``
    BEFORE any message row is appended: owner → metadata, foreign/unknown
    → NotFoundError (indistinguishable).
    """

    async def test_get_conversation_with_owner_returns_metadata(self) -> None:
        """The owner resolves the conversation's metadata."""
        store = InMemoryConversationStore()
        owner_id = uuid4()
        project_id = uuid4()

        conv_id = await store.create_conversation(project_id, owner_id, "Hello")

        conv = await store.get_conversation(conv_id, owner_id)

        assert conv.id == conv_id
        assert conv.project_id == project_id
        assert conv.user_id == owner_id

    async def test_get_conversation_with_foreign_user_raises_not_found(self) -> None:
        """Another user's conversation raises NotFoundError (HTTP 404)."""
        store = InMemoryConversationStore()
        owner_id, attacker_id = uuid4(), uuid4()

        conv_id = await store.create_conversation(None, owner_id, "Private")

        with pytest.raises(NotFoundError):
            await store.get_conversation(conv_id, attacker_id)

    async def test_get_conversation_with_unknown_conversation_raises_not_found(self) -> None:
        """An unknown conversation_id raises NotFoundError (HTTP 404)."""
        store = InMemoryConversationStore()

        with pytest.raises(NotFoundError):
            await store.get_conversation(uuid4(), uuid4())

    async def test_get_conversation_with_owner_projectless_returns_none_project(self) -> None:
        """A project-less owned conversation resolves with project_id None."""
        store = InMemoryConversationStore()
        owner_id = uuid4()

        conv_id = await store.create_conversation(None, owner_id, "Craft question")

        conv = await store.get_conversation(conv_id, owner_id)

        assert conv.project_id is None


class TestOwnershipEnforcement:
    """History access is scoped to the conversation's owner.

    Foreign and unknown conversations are indistinguishable — both raise
    NotFoundError (mapped to HTTP 404 by the global handler) so callers
    cannot probe for the existence of other users' conversations.
    """

    async def test_get_history_with_owner_returns_messages(self) -> None:
        """The owner receives the conversation's messages."""
        store = InMemoryConversationStore()
        user_id = uuid4()

        conv_id = await store.create_conversation(None, user_id, "Mine")

        history = await store.get_history(conv_id, user_id)

        assert [m.content for m in history] == ["Mine"]

    async def test_get_history_with_foreign_user_raises_not_found(self) -> None:
        """Another user's conversation raises NotFoundError (HTTP 404)."""
        store = InMemoryConversationStore()
        owner_id, attacker_id = uuid4(), uuid4()

        conv_id = await store.create_conversation(None, owner_id, "Secret")

        with pytest.raises(NotFoundError):
            await store.get_history(conv_id, attacker_id)

    async def test_get_history_with_unknown_conversation_raises_not_found(self) -> None:
        """An unknown conversation_id raises NotFoundError, like a foreign one."""
        store = InMemoryConversationStore()

        with pytest.raises(NotFoundError):
            await store.get_history(uuid4(), uuid4())

    async def test_get_history_owned_but_empty_returns_empty_list(self) -> None:
        """An owned conversation with no messages yields [] — not NotFoundError."""
        store = InMemoryConversationStore()
        user_id = uuid4()

        conv_id = await store.create_conversation(None, user_id, "Seed")

        await store.clear_history(conv_id, user_id)
        history = await store.get_history(conv_id, user_id)

        assert history == []

    async def test_clear_history_with_foreign_user_raises_not_found_and_keeps_messages(
        self,
    ) -> None:
        """A foreign user cannot clear the conversation; messages survive."""
        store = InMemoryConversationStore()
        owner_id, attacker_id = uuid4(), uuid4()

        conv_id = await store.create_conversation(None, owner_id, "Keep me")

        with pytest.raises(NotFoundError):
            await store.clear_history(conv_id, attacker_id)

        history = await store.get_history(conv_id, owner_id)
        assert [m.content for m in history] == ["Keep me"]

    async def test_clear_history_with_owner_removes_messages(self) -> None:
        """The owner's clear succeeds and the conversation stays readable."""
        store = InMemoryConversationStore()
        user_id = uuid4()

        conv_id = await store.create_conversation(None, user_id, "Bye")

        await store.clear_history(conv_id, user_id)

        assert await store.get_history(conv_id, user_id) == []

    async def test_clear_history_with_unknown_conversation_raises_not_found(self) -> None:
        """Clearing an unknown conversation raises NotFoundError (HTTP 404)."""
        store = InMemoryConversationStore()

        with pytest.raises(NotFoundError):
            await store.clear_history(uuid4(), uuid4())

    async def test_get_conversation_project_id_with_foreign_user_raises_not_found(
        self,
    ) -> None:
        """Project resolution is ownership-scoped as well."""
        store = InMemoryConversationStore()
        owner_id, attacker_id = uuid4(), uuid4()
        project_id = uuid4()

        conv_id = await store.create_conversation(project_id, owner_id, "Hello")

        with pytest.raises(NotFoundError):
            await store.get_conversation_project_id(conv_id, attacker_id)

    async def test_get_conversation_project_id_with_owner_returns_project(self) -> None:
        """The owner resolves the conversation's project_id."""
        store = InMemoryConversationStore()
        owner_id = uuid4()
        project_id = uuid4()

        conv_id = await store.create_conversation(project_id, owner_id, "Hello")

        assert await store.get_conversation_project_id(conv_id, owner_id) == project_id
