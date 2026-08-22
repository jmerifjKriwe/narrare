"""Unit tests for core chat contracts after NOTES-001 §6b changes."""

from __future__ import annotations

import inspect
from uuid import uuid4

from narrare_core.chat.contracts import ChatRequest


class TestChatRequestOptionals:
    def test_legacy_positional_shape_still_works(self) -> None:
        """Regression: existing callers pass (project_id, message) positionally."""
        project_id = uuid4()
        request = ChatRequest(project_id, "hello")
        assert request.project_id == project_id
        assert request.message == "hello"
        assert request.conversation_id is None
        assert request.note_id is None

    def test_projectless_request_for_global_note_chat(self) -> None:
        request = ChatRequest(message="discuss this", note_id=uuid4())
        assert request.project_id is None
        assert request.note_id is not None

    def test_all_defaults_construct(self) -> None:
        request = ChatRequest()
        assert request.project_id is None
        assert request.message == ""


class TestConversationStoreSignature:
    def test_abstract_create_conversation_accepts_none_project(self) -> None:
        """The ABC must allow project-less conversations (NOTES-001 §6b)."""
        from narrare_core.chat.conversation_store import ConversationStore

        annotation = (
            inspect.signature(ConversationStore.create_conversation)
            .parameters["project_id"]
            .annotation
        )
        assert "None" in annotation or "Optional" in annotation
