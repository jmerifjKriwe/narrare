"""Unit tests for ChatAgent — instantiation and configuration.

Verifies that ``ChatAgent.__init__`` correctly wires HistoryPolicy
via the NarrareAgent base class, and that the feature system prompt
(ADR-046) is forwarded to the pydantic-ai system channel.

Uses pydantic-ai ``TestModel`` — no real LLM calls.
"""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest
from pydantic_ai.messages import ModelRequest, SystemPromptPart
from pydantic_ai.models.test import TestModel

from narrare_core.agents.history_policy import HistoryPolicy
from narrare_core.chat.chat_agent import ChatAgent
from narrare_core.chat.chat_deps import ChatDeps
from narrare_core.prompts import PromptComposer
from narrare_core.prompts.context import PromptContext

_SYSTEM_MARKER = "FEATURE_CHAT_CORE_SYSTEM_MARKER_42"


class TestChatAgentInstantiation:
    """ChatAgent initialises correctly with model and HistoryPolicy."""

    def test_instantiates_with_test_model(self) -> None:
        """ChatAgent can be constructed with a pydantic-ai TestModel."""
        model = TestModel()
        agent = ChatAgent(model=model)

        assert agent is not None

    def test_uses_conversational_history_policy(self) -> None:
        """ChatAgent uses HistoryPolicy.CONVERSATIONAL (ADR-034)."""
        model = TestModel()
        agent = ChatAgent(model=model)

        assert agent.history_policy == HistoryPolicy.CONVERSATIONAL

    def test_system_prompt_defaults_to_none(self) -> None:
        """Omitting system_prompt keeps the agent usable (backward compatible)."""
        agent = ChatAgent(model=TestModel())

        # The agent must still construct and be runnable without a feature
        # system prompt — existing callers (evals, tests) rely on this.
        assert agent.history_policy == HistoryPolicy.CONVERSATIONAL


class TestChatAgentSystemPromptForwarding:
    """ADR-046: the feature system prompt reaches the pydantic-ai system channel.

    ChatAgent must forward its ``system_prompt`` constructor argument to the
    underlying pydantic-ai ``Agent`` so it lands in the SYSTEM channel — never
    in the user channel.
    """

    async def test_feature_system_prompt_appears_in_system_channel(self) -> None:
        """The ``system_prompt`` body is present as a SystemPromptPart."""
        import asyncio

        model = TestModel(custom_output_text="ok")
        agent = ChatAgent(model=model, system_prompt=_SYSTEM_MARKER)
        deps = ChatDeps(
            prompt_composer=MagicMock(spec=PromptComposer),
            context=PromptContext(language="en"),
            user_prompt="hello",
        )

        # Drive the underlying pydantic-ai agent to capture the assembled
        # ModelRequest parts (NarrareAgent.run discards the result object).
        result = await asyncio.wait_for(
            agent._agent.run("hello", deps=deps),
            timeout=5.0,
        )

        system_bodies: list[str] = []
        for message in result.all_messages():
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, SystemPromptPart):
                        system_bodies.append(str(part.content))

        assert any(_SYSTEM_MARKER in body for body in system_bodies), (
            "Feature system_prompt must be forwarded to the pydantic-ai system "
            f"channel; system parts were: {system_bodies!r}"
        )

    async def test_user_prompt_not_polluted_by_system_when_no_system_prompt(self) -> None:
        """With system_prompt=None, no feature marker leaks (sanity baseline)."""
        import asyncio

        model = TestModel(custom_output_text="ok")
        agent = ChatAgent(model=model, system_prompt=None)
        deps = ChatDeps(
            prompt_composer=MagicMock(spec=PromptComposer),
            context=PromptContext(language="en"),
            user_prompt="plain user text",
        )

        result = await asyncio.wait_for(
            agent._agent.run("plain user text", deps=deps),
            timeout=5.0,
        )

        system_bodies: list[str] = []
        for message in result.all_messages():
            if isinstance(message, ModelRequest):
                for part in message.parts:
                    if isinstance(part, SystemPromptPart):
                        system_bodies.append(str(part.content))

        assert not any(_SYSTEM_MARKER in body for body in system_bodies)


class TestChatAgentCapabilities:
    """ADR-026 / AC #4 (CR-AUFG-02-04): ChatAgent retains guaranteed capabilities.

    ``ChatAgent`` is exported from ``narrare_core.chat`` (not
    ``narrare_core.agents``), so it is NOT reached by
    ``test_all_production_agent_classes_inherit_adr026_capabilities`` (which
    iterates ``narrare_core.agents.__all__``). This class provides direct
    coverage: even when an ADR-046 ``system_prompt`` is supplied, the
    guaranteed ``NarrareMeta`` + ``NarrareUniversalRules`` capabilities must
    still be injected into the pydantic-ai ``Agent``.

    The capture technique mirrors the one in
    ``tests/unit/core/agents/test_base.py`` — we monkeypatch the stable
    ``Agent`` symbol in ``narrare_core.agents.base`` rather than reaching into
    pydantic-ai private internals.
    """

    @pytest.mark.parametrize("system_prompt", [_SYSTEM_MARKER, None])
    def test_guaranteed_capabilities_retained_with_or_without_system_prompt(
        self,
        system_prompt: str | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NarrareMeta + NarrareUniversalRules survive the system_prompt path.

        Regression guard for the ADR-046 change: adding a feature
        ``system_prompt`` to the constructor must NOT displace the guaranteed
        ADR-026 capabilities. Verified both with and without a system_prompt.
        """
        import narrare_core.agents.base as base_module
        from narrare_core.agents.capabilities import (
            NarrareMeta,
            NarrareUniversalRules,
        )

        class CapturingPydanticAgent:
            """Records the kwargs handed to the pydantic-ai ``Agent``."""

            calls: ClassVar[list[dict[str, Any]]] = []

            def __init__(self, **kwargs: Any) -> None:
                self.calls.append(kwargs)

            def output_validator(self, validator: Any) -> Any:
                return validator

            def tool(self, tool_func: Any) -> Any:
                return tool_func

        monkeypatch.setattr(base_module, "Agent", CapturingPydanticAgent)

        # Construct ChatAgent exactly as ChatService does post-ADR-046.
        # ``chat_agent_cls`` is typed ``Any`` (matching the pattern in
        # ``tests/unit/core/agents/test_base.py``) so ``object()`` is accepted
        # as the model — only construction matters here, not a real model.
        chat_agent_cls: Any = ChatAgent
        chat_agent_cls(model=object(), system_prompt=system_prompt)

        assert CapturingPydanticAgent.calls, (
            "ChatAgent did not reach the NarrareAgent base constructor."
        )
        capabilities = CapturingPydanticAgent.calls[-1]["capabilities"]
        capability_types = {type(capability) for capability in capabilities}
        assert NarrareMeta in capability_types, (
            "ChatAgent must inject NarrareMeta even with a feature system_prompt."
        )
        assert NarrareUniversalRules in capability_types, (
            "ChatAgent must inject NarrareUniversalRules even with a system_prompt."
        )
