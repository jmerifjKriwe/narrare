"""Unit tests for ChatService project-link ownership (P-SEC hardening).

A non-null ``project_id`` must belong to the caller — notes
``_validate_link`` semantics: foreign and unknown novels are
indistinguishable (both NotFoundError → HTTP 404 via the global handler),
so there is no enumeration oracle and project-scoped enrichment can never
correlate another user's novel.

Uses the shared fixtures from tests/unit/api/chat/conftest.py
(``service_with_novel_lookup`` / ``novel_lookup``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from narrare_core.agents.base import StreamEvent
from narrare_core.chat.chat_agent import ChatAgent
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from tests.unit.api.chat.conftest import FakeNovelLookup

    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore


class TestProjectOwnership:
    """A non-null ``project_id`` must belong to the caller (IDOR hardening)."""

    async def test_ask_with_foreign_project_creates_no_conversation_and_raises(
        self,
        service_with_novel_lookup: ChatService,
        novel_lookup: FakeNovelLookup,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """IDOR regression: another user's novel as project_id → 404, and the
        caller-owned conversation referencing it is NEVER created."""
        from tests.unit.api.chat.conftest import _make_request

        owner_id, attacker_id = uuid4(), uuid4()
        novel_id = uuid4()
        novel_lookup.seed_owned(novel_id, owner_id)

        request = _make_request(message="Craft question")
        request.project_id = novel_id

        with pytest.raises(NotFoundError):
            await service_with_novel_lookup.ask(request, attacker_id)

        # No conversation row was created — the store stayed empty.
        assert in_memory_store._conversations == {}  # pyright: ignore[reportPrivateUsage] — fake store has no public counter; "no row" is the security assertion

    async def test_ask_with_unknown_project_raises_not_found(
        self,
        service_with_novel_lookup: ChatService,
    ) -> None:
        """A project_id nobody owns 404s (indistinguishable from foreign)."""
        from tests.unit.api.chat.conftest import _make_request

        request = _make_request(message="Craft question")
        request.project_id = uuid4()

        with pytest.raises(NotFoundError):
            await service_with_novel_lookup.ask(request, uuid4())

    async def test_ask_with_owned_project_creates_conversation(
        self,
        service_with_novel_lookup: ChatService,
        novel_lookup: FakeNovelLookup,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """Happy path regression: the caller's own novel still works."""
        from tests.unit.api.chat.conftest import _async_gen, _make_request

        user_id = uuid4()
        novel_id = uuid4()
        novel_lookup.seed_owned(novel_id, user_id)

        request = _make_request(message="About my novel")
        request.project_id = novel_id

        mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
        mock_agent.run_stream = lambda *a, **kw: _async_gen(
            StreamEvent(type="token", text="Hi"),
            StreamEvent(type="done", text="Hi", usage={}, new_messages=[]),
        )

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            events = []
            async for event in await service_with_novel_lookup.ask(request, user_id):
                events.append(event)

        assert events[0]["type"] == "meta"
        conv_id = UUID(str(events[0]["conversation_id"]))
        stored_project = await in_memory_store.get_conversation_project_id(conv_id, user_id)
        assert stored_project == novel_id

    async def test_ask_existing_conversation_with_foreign_project_raises(
        self,
        service_with_novel_lookup: ChatService,
        novel_lookup: FakeNovelLookup,
        in_memory_store: InMemoryConversationStore,
    ) -> None:
        """Enrichment vector: a foreign project_id on an OWNED conversation 404s
        too — ``project_id`` feeds invocation enrichment correlation, which
        must never reference another user's novel."""
        from tests.unit.api.chat.conftest import _make_request

        owner_id, attacker_id = uuid4(), uuid4()
        novel_id = uuid4()
        novel_lookup.seed_owned(novel_id, owner_id)

        conv_id = await in_memory_store.create_conversation(None, owner_id, "Earlier")

        request = _make_request(message="Continue", conversation_id=conv_id)
        request.project_id = novel_id

        with pytest.raises(NotFoundError):
            await service_with_novel_lookup.ask(request, attacker_id)

        # Nothing was appended to the owned conversation either.
        history = await in_memory_store.get_history(conv_id, owner_id)
        assert [m.content for m in history] == ["Earlier"]
