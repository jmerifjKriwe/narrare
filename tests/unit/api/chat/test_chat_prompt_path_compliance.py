"""Prompt-Path-Compliance tests for ChatService (ADR-046 / CR-AUFG-02-04).

These tests verify HOW the chat prompt is resolved and injected — not just
WHAT it says. They guard against the CR-02 drift where ``composed.system``
was concatenated into the user prompt (``full_prompt = f"{composed.system}
\n\n{composed.user}"``) instead of being passed as agent system/instructions.

See:
    - ADR-046 (Prompt-Path-Compliance)
    - docs/features/remediation/cr-02-prompt-path-retrofit.md § CR-AUFG-02-04
    - RULE-02 / RULE-02a / RULE-02b
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from narrare_core.agents.base import StreamEvent
from narrare_core.chat.chat_agent import ChatAgent
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService
    from narrare.chat.conversation_store import SQLAlchemyConversationStore

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------
#
# Distinctive tokens placed in the system and user bodies returned by the
# mocked PromptComposer. Under prompt-path compliance:
#   - ``_SYSTEM_MARKER`` MUST appear in the ``ChatAgent`` constructor
#     ``system_prompt`` kwarg (the system channel).
#   - ``_SYSTEM_MARKER`` MUST NOT appear in the user-channel ``prompt``
#     argument passed to ``ChatAgent.run_stream()``.
#   - ``_USER_MARKER`` MUST appear in the user-channel ``prompt`` argument.
#
# They are deliberately unique strings that would never occur in ordinary
# chat text, so the assertions are unambiguous.
_SYSTEM_MARKER = "FEATURE_CHAT_SYSTEM_BODY_MARKER_7f3a"
_USER_MARKER = "FEATURE_CHAT_USER_MESSAGE_MARKER_2c91"


def _make_chat_service(system: str, user: str) -> tuple[ChatService, AsyncMock]:
    """Build a ChatService whose PromptComposer returns given system/user bodies.

    Returns the service and the mocked composer so tests can assert on
    ``composer.build`` call arguments.
    """
    from tests.unit.api.chat.conftest import _make_config, _make_mock_registry, _static_resolution

    from narrare.chat.chat_service import ChatService
    from narrare_core.chat.conversation_store import InMemoryConversationStore

    composer = AsyncMock(name="compliance_composer")
    composer.build = AsyncMock(name="compliance_composer.build")
    composer.build.return_value = ComposedPrompt(system=system, user=user)

    service = ChatService(
        prompt_composer=composer,
        model_registry=_make_mock_registry(),
        conversation_store=cast(
            "SQLAlchemyConversationStore",
            InMemoryConversationStore(),
        ),
        model_resolution=_static_resolution(_make_config()),
    )
    return service, composer


async def _drain(service: ChatService, message: str) -> list[dict[str, object]]:
    """Run ``service.ask()`` for a fresh conversation and collect SSE events."""
    from tests.unit.api.chat.conftest import _make_request

    request = _make_request(message=message)
    events: list[dict[str, object]] = []
    async for event in await service.ask(request, uuid4()):
        events.append(event)
    return events


def _recording_agent() -> tuple[MagicMock, dict[str, object]]:
    """Return a mock ChatAgent plus a dict that captures constructor kwargs.

    ``mock_agent.run_stream`` is a MagicMock (not a bare lambda) so that
    ``call_args`` captures the ``prompt=`` argument.
    """
    from tests.unit.api.chat.conftest import _async_gen

    captured_kwargs: dict[str, object] = {}
    mock_agent = MagicMock(name="compliance_agent", spec=ChatAgent)
    # ``mock_agent`` already carries ``spec=ChatAgent``, so ``run_stream`` is
    # an auto-specced child mock — configure ``side_effect`` on it directly
    # rather than replacing it with a bare MagicMock (RULE-TEST-01).
    mock_agent.run_stream.side_effect = lambda *a, **kw: _async_gen(
        StreamEvent(type="done", text="ok", usage={}, new_messages=[]),
    )
    return mock_agent, captured_kwargs


# ---------------------------------------------------------------------------
# AC #1 — LLMIntent.CHAT resolves through PromptComposer
# ---------------------------------------------------------------------------


class TestChatPromptPathCompliance:
    """Prompt-Path-Compliance for ChatService (ADR-046 / CR-AUFG-02-04)."""

    async def test_chat_service_resolves_via_prompt_composer(self) -> None:
        """AC #1: ChatService must call ``PromptComposer.build(LLMIntent.CHAT, ...)``.

        Regression guard: the chat prompt must be assembled by the
        PromptComposer cascade, never inline.
        """
        system = f"{_SYSTEM_MARKER} You are Narrare, the author's writing companion."
        user = f"{_USER_MARKER} Hello, can you help me with my protagonist?"
        service, composer = _make_chat_service(system=system, user=user)
        mock_agent, _ = _recording_agent()

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            await _drain(service, message="Help me with my protagonist.")

        composer.build.assert_awaited_once()
        call = composer.build.call_args
        assert call is not None
        # Intent is the first positional argument.
        assert call.args[0] is LLMIntent.CHAT, (
            f"Expected PromptComposer.build() to be called with LLMIntent.CHAT, "
            f"got {call.args[0]!r}"
        )
        # The user message must be forwarded as user_prompt (user-channel data).
        assert call.kwargs.get("user_prompt") == "Help me with my protagonist."

    async def test_system_channel_receives_feature_prompt_and_user_channel_does_not(
        self,
    ) -> None:
        """AC #2 + #3 + #6: channel separation.

        - The ``ChatAgent`` constructor receives ``system_prompt`` containing
          the feature system body (``_SYSTEM_MARKER``).
        - The ``prompt`` passed to ``run_stream()`` does NOT contain the
          feature system body, and DOES contain the user body.
        """
        system = (
            f"{_SYSTEM_MARKER} You are Narrare, the author's writing companion. "
            "Answer directly and practically."
        )
        user = f"{_USER_MARKER} Help me with my protagonist."
        service, _ = _make_chat_service(system=system, user=user)
        mock_agent, captured_kwargs = _recording_agent()

        with patch(
            "narrare_core.chat.chat_agent.ChatAgent",
            side_effect=lambda *args, **kwargs: _capture_and_return(
                captured_kwargs, kwargs, mock_agent
            ),
        ):
            await _drain(service, message="Help me with my protagonist.")

        # AC #2: ChatAgent constructed with a non-None system_prompt carrying
        # the feature system body.
        system_prompt = captured_kwargs.get("system_prompt")
        assert system_prompt is not None, (
            "ChatAgent must be constructed with a system_prompt (ADR-046)."
        )
        assert _SYSTEM_MARKER in str(system_prompt), (
            "ChatAgent.system_prompt must contain the feature system body."
        )

        # AC #3 + #6: user-channel prompt must NOT contain the system body,
        # and MUST contain the user body.
        run_call = mock_agent.run_stream.call_args
        assert run_call is not None, "ChatAgent.run_stream was never called."
        prompt_arg = run_call.kwargs.get("prompt")
        assert prompt_arg is not None, (
            "run_stream must be called with an explicit prompt= argument."
        )
        assert _SYSTEM_MARKER not in str(prompt_arg), (
            f"REGRESSION: feature system prompt leaked into the user channel. prompt={prompt_arg!r}"
        )
        assert _USER_MARKER in str(prompt_arg), (
            "User-channel prompt must contain the composed user message body."
        )

    async def test_user_prompt_is_exactly_composed_user(self) -> None:
        """AC #3 (strictness): ``prompt`` equals ``composed.user`` verbatim.

        The user channel must carry only the PromptComposer's user body —
        no trailing/leading system content, no concatenation artifact.
        """
        expected_user = f"{_USER_MARKER} A very specific user message body for exact match."
        service, _ = _make_chat_service(
            system=f"{_SYSTEM_MARKER} system body",
            user=expected_user,
        )
        mock_agent, _ = _recording_agent()

        with patch("narrare_core.chat.chat_agent.ChatAgent", return_value=mock_agent):
            from tests.unit.api.chat.conftest import _make_request

            request = _make_request(message="ignored-by-composer-mock")
            async for _ in await service.ask(request, uuid4()):
                pass

        run_call = mock_agent.run_stream.call_args
        assert run_call is not None
        assert run_call.kwargs.get("prompt") == expected_user, (
            "User-channel prompt must be exactly composed.user (no concatenation)."
        )


def _capture_and_return(
    captured: dict[str, object],
    kwargs: dict[str, object],
    mock_agent: MagicMock,
) -> MagicMock:
    """Side-effect helper: record constructor kwargs and return the mock agent."""
    captured.update(kwargs)
    return mock_agent
