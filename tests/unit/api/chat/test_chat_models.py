"""Unit tests for narrare.chat.models — SQLAlchemy ORM models.

Tests model instantiation and ``__repr__`` methods. No database
session required — these are pure object-construction tests.
"""

from __future__ import annotations

from uuid import uuid4

from narrare.chat.models import ChatConversation, ChatMessage

# ---------------------------------------------------------------------------
# ChatConversation
# ---------------------------------------------------------------------------


class TestChatConversationModel:
    """Tests for the ChatConversation ORM model."""

    def test_instantiation_assigns_required_fields(self) -> None:
        """ChatConversation stores project_id and user_id."""
        project_id = uuid4()
        user_id = uuid4()

        conv = ChatConversation(project_id=project_id, user_id=user_id)

        assert conv.project_id == project_id
        assert conv.user_id == user_id

    def test_instantiation_accepts_explicit_id(self) -> None:
        """ChatConversation accepts an explicit id."""
        conv_id = uuid4()
        conv = ChatConversation(id=conv_id, project_id=uuid4(), user_id=uuid4())

        assert conv.id == conv_id

    def test_title_defaults_to_none(self) -> None:
        """ChatConversation.title is nullable (defaults to None)."""
        conv = ChatConversation(project_id=uuid4(), user_id=uuid4())

        assert conv.title is None

    def test_repr_includes_id_project_id_and_title(self) -> None:
        """__repr__ produces a readable representation."""
        project_id = uuid4()
        conv = ChatConversation(
            project_id=project_id,
            user_id=uuid4(),
            title="My Novel",
        )

        repr_str = repr(conv)

        assert "ChatConversation" in repr_str
        assert str(conv.id) in repr_str
        assert str(project_id) in repr_str
        assert "'My Novel'" in repr_str


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------


class TestChatMessageModel:
    """Tests for the ChatMessage ORM model."""

    def test_instantiation_assigns_required_fields(self) -> None:
        """ChatMessage stores conversation_id, role, and content."""
        conv_id = uuid4()

        msg = ChatMessage(
            conversation_id=conv_id,
            role="user",
            content="Hello!",
        )

        assert msg.conversation_id == conv_id
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_instantiation_accepts_explicit_id(self) -> None:
        """ChatMessage accepts an explicit id."""
        msg_id = uuid4()
        msg = ChatMessage(
            id=msg_id,
            conversation_id=uuid4(),
            role="assistant",
            content="Hi!",
        )

        assert msg.id == msg_id

    def test_tokens_defaults_to_none(self) -> None:
        """ChatMessage.tokens is nullable (defaults to None)."""
        msg = ChatMessage(
            conversation_id=uuid4(),
            role="user",
            content="No tokens",
        )

        assert msg.tokens is None

    def test_repr_includes_role_and_tokens(self) -> None:
        """__repr__ produces a readable representation."""
        msg = ChatMessage(
            conversation_id=uuid4(),
            role="assistant",
            content="Hello",
            tokens=42,
        )

        repr_str = repr(msg)

        assert "ChatMessage" in repr_str
        assert "'assistant'" in repr_str
        assert "42" in repr_str
