# tests/unit/api/chat/test_chat_service_note.py
"""Unit tests for note context injection into chat (NOTES-001 §6b, RULE-02).

The note must travel as RUNTIME INPUT: the context block appears in the
persisted user message and in the composer's user_prompt — never in a
system/task template. A missing/unowned note degrades gracefully (warn +
proceed, RULE-11).

``ChatAgent`` is patched per the conftest pattern: the real agent rejects
the mock registry model (see test_chat_service_projectless.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from structlog.testing import capture_logs
from tests.unit.api.chat.conftest import _async_gen

from narrare_core.chat.contracts import ChatRequest
from narrare_core.notes.contracts import NoteSnapshot

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore
    from narrare_core.chat.conversation_store import InMemoryConversationStore
    from narrare_core.llm import ModelRegistry
    from narrare_core.notes.contracts import NoteLookupProtocol
    from narrare_core.prompts import PromptComposer


def _mock_chat_agent() -> MagicMock:
    """Build a ChatAgent mock streaming one token + done (conftest pattern)."""
    from narrare_core.agents.base import StreamEvent
    from narrare_core.chat.chat_agent import ChatAgent

    mock_agent = MagicMock(name="mock_agent", spec=ChatAgent)
    mock_agent.run_stream = lambda *a, **kw: _async_gen(
        StreamEvent(type="token", text="Answer"),
        StreamEvent(type="done", text="Answer", usage={}, new_messages=[]),
    )
    return mock_agent


def _echo_mock_composer() -> AsyncMock:
    """Mock PromptComposer echoing ``user_prompt`` into ``ComposedPrompt.user``.

    The conftest composer returns a FIXED user string ("Hello!"), which
    hides whether the effective message actually flows downstream. This
    variant closes the loop: message → composer ``user_prompt`` kwarg →
    ``composed.user`` → agent ``run_stream(prompt=...)``.
    """
    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock()

    async def _build(*_args: object, **kwargs: object) -> ComposedPrompt:
        return ComposedPrompt(
            system="You are a helpful writing assistant.",
            user=str(kwargs.get("user_prompt", "")),
        )

    composer.build = AsyncMock(side_effect=_build)
    return composer


def _recording_chat_agent(prompts: list[str]) -> MagicMock:
    """ChatAgent mock that records ``run_stream``'s ``prompt`` kwarg.

    Streams one token + done like the conftest pattern, while appending
    each call's ``prompt`` to ``prompts`` for agent-side assertions.
    """
    from narrare_core.agents.base import StreamEvent
    from narrare_core.chat.chat_agent import ChatAgent

    mock_agent = MagicMock(name="recording_agent", spec=ChatAgent)

    def _record_and_stream(*_args: object, **kwargs: object) -> object:
        prompts.append(str(kwargs.get("prompt")))
        return _async_gen(
            StreamEvent(type="token", text="Answer"),
            StreamEvent(type="done", text="Answer", usage={}, new_messages=[]),
        )

    mock_agent.run_stream = _record_and_stream
    return mock_agent


class FakeNoteLookup:
    """NoteLookupProtocol double with one owned note."""

    def __init__(self, snapshot: NoteSnapshot | None) -> None:
        self._snapshot = snapshot
        self.calls: list[tuple[object, object]] = []

    async def get_note_snapshot(self, note_id: object, user_id: object) -> NoteSnapshot | None:
        self.calls.append((note_id, user_id))
        return self._snapshot


def _make_snapshot(note_id: UUID) -> NoteSnapshot:
    return NoteSnapshot(
        id=note_id,
        title="Twist",
        content="The aunt is the culprit.",
        note_type="idea",
        tags=["plot"],
    )


def _make_service(
    mock_composer: object,
    mock_registry: object,
    in_memory_store: object,
    mock_config: object,
    lookup: FakeNoteLookup | NoteLookupProtocol | None,
) -> ChatService:
    from tests.unit.api.chat.conftest import _static_resolution

    from narrare.chat.chat_service import ChatService

    return ChatService(
        prompt_composer=cast("PromptComposer", mock_composer),
        model_registry=cast("ModelRegistry", mock_registry),
        conversation_store=cast("SQLAlchemyConversationStore", in_memory_store),
        model_resolution=_static_resolution(mock_config),
        note_lookup=lookup,
    )


class TestNoteInjection:
    async def test_note_block_prepended_to_persisted_user_message(
        self,
        mock_composer: object,
        mock_registry: object,
        in_memory_store: object,
        mock_config: object,
    ) -> None:
        note_id = uuid4()
        service = _make_service(
            mock_composer,
            mock_registry,
            in_memory_store,
            mock_config,
            FakeNoteLookup(_make_snapshot(note_id)),
        )
        user_id = uuid4()
        request = ChatRequest(message="What do you think?", note_id=note_id)

        events = []
        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_mock_chat_agent(),
        ):
            stream = await service.ask(request, user_id)
            async for event in stream:
                events.append(event)

        history = await cast("InMemoryConversationStore", in_memory_store).get_history(
            UUID(str(events[0]["conversation_id"])),
            user_id,
        )
        user_messages = [m for m in history if m.role == "user"]
        assert len(user_messages) == 1
        assert user_messages[0].content.startswith("[Note — idea [plot]]")
        assert "The aunt is the culprit." in user_messages[0].content
        assert user_messages[0].content.endswith("What do you think?")

    async def test_user_prompt_passed_to_composer_contains_note(
        self,
        in_memory_store: object,
        mock_registry: object,
        mock_config: object,
    ) -> None:
        from tests.unit.api.chat.conftest import _make_mock_composer

        composer = _make_mock_composer()
        note_id = uuid4()
        service = _make_service(
            composer,
            mock_registry,
            in_memory_store,
            mock_config,
            FakeNoteLookup(_make_snapshot(note_id)),
        )
        request = ChatRequest(message="Discuss", note_id=note_id)

        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_mock_chat_agent(),
        ):
            stream = await service.ask(request, uuid4())
            async for _event in stream:
                pass

        composer.build.assert_called()
        kwargs = composer.build.call_args.kwargs
        assert kwargs["user_prompt"].startswith("[Note — idea [plot]]")

    async def test_note_block_reaches_agent_run_stream_prompt(
        self,
        mock_registry: object,
        in_memory_store: object,
        mock_config: object,
    ) -> None:
        """The effective message reaches the AGENT side (loop closure).

        With an echo composer (``ComposedPrompt.user`` mirrors the
        ``user_prompt`` kwarg) and a recording agent mock, the prompt
        passed to ``ChatAgent.run_stream`` must carry the note block
        prefix and end with the raw message — proving the injection
        travels the full message → composer → ``composed.user`` → agent
        chain, not just into persistence.
        """
        composer = _echo_mock_composer()
        prompts: list[str] = []
        note_id = uuid4()
        service = _make_service(
            composer,
            mock_registry,
            in_memory_store,
            mock_config,
            FakeNoteLookup(_make_snapshot(note_id)),
        )
        request = ChatRequest(message="Discuss", note_id=note_id)

        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_recording_chat_agent(prompts),
        ):
            stream = await service.ask(request, uuid4())
            async for _event in stream:
                pass

        assert prompts, "agent run_stream must have been called"
        assert prompts[0].startswith("[Note — idea [plot]]")
        assert prompts[0].endswith("Discuss")

    async def test_unwired_lookup_logs_note_unavailable_and_proceeds_with_raw_message(
        self,
        mock_registry: object,
        in_memory_store: object,
        mock_config: object,
    ) -> None:
        """note_lookup=None + note_id set → chat_note_unavailable + raw message.

        RULE-11 graceful degradation: an unwired lookup (snapshot stays
        ``None``) must not fail the conversation — the warning
        ``chat_note_unavailable`` is emitted and the persisted user
        message is exactly the raw request message.
        """
        from tests.unit.api.chat.conftest import _make_mock_composer

        composer = _make_mock_composer()
        service = _make_service(composer, mock_registry, in_memory_store, mock_config, None)
        note_id = uuid4()
        user_id = uuid4()
        request = ChatRequest(message="Discuss", note_id=note_id)

        events = []
        with (
            patch(
                "narrare_core.chat.chat_agent.ChatAgent",
                return_value=_mock_chat_agent(),
            ),
            capture_logs() as logs,
        ):
            stream = await service.ask(request, user_id)
            async for event in stream:
                events.append(event)

        unavailable = [e for e in logs if e.get("event") == "chat_note_unavailable"]
        assert unavailable, "expected a chat_note_unavailable warning"
        assert unavailable[0].get("note_id") == str(note_id)

        history = await cast("InMemoryConversationStore", in_memory_store).get_history(
            UUID(str(events[0]["conversation_id"])),
            user_id,
        )
        user_messages = [m for m in history if m.role == "user"]
        assert len(user_messages) == 1
        assert user_messages[0].content == "Discuss"

    async def test_missing_note_degrades_gracefully(
        self,
        mock_composer: object,
        mock_registry: object,
        in_memory_store: object,
        mock_config: object,
    ) -> None:
        service = _make_service(
            mock_composer,
            mock_registry,
            in_memory_store,
            mock_config,
            FakeNoteLookup(None),
        )
        request = ChatRequest(message="Discuss", note_id=uuid4())

        events = []
        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_mock_chat_agent(),
        ):
            stream = await service.ask(request, uuid4())
            async for event in stream:
                events.append(event)

        assert events[0]["type"] == "meta"  # no raise — RULE-11

    async def test_no_note_id_no_lookup(
        self,
        mock_composer: object,
        mock_registry: object,
        in_memory_store: object,
        mock_config: object,
    ) -> None:
        lookup = FakeNoteLookup(_make_snapshot(uuid4()))
        service = _make_service(mock_composer, mock_registry, in_memory_store, mock_config, lookup)
        request = ChatRequest(message="Just chatting")

        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            return_value=_mock_chat_agent(),
        ):
            stream = await service.ask(request, uuid4())
            async for _event in stream:
                pass

        assert lookup.calls == []
