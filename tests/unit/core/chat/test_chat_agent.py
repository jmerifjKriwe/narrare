"""Unit tests for ChatAgent — instantiation and configuration.

Verifies that ``ChatAgent.__init__`` correctly wires HistoryPolicy
via the NarrareAgent base class.

Uses pydantic-ai ``TestModel`` — no real LLM calls.
"""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents.history_policy import HistoryPolicy
from narrare_core.chat.chat_agent import ChatAgent


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
