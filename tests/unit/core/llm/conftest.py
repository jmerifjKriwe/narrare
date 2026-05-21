"""Shared fixtures for core/llm/ unit tests.

Provides pydantic-ai testing tools (TestModel, FunctionModel) for tests
that exercise the registry->agent bridge. These replace hand-rolled fakes
with pydantic-ai's built-in test models, which stay in sync with the
library automatically.

See: docs/development/testing-standards.md — RULE-TEST-01
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai.models.test import (  # narrare: allow reason="test fixtures"
    TestModel,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig


@pytest.fixture
def write_config() -> ResolvedModelConfig:
    """Default ResolvedModelConfig for gateway tests."""
    from narrare_core.llm.intents import ResolvedModelConfig

    return ResolvedModelConfig(
        provider_name="anthropic",
        model_id="claude-sonnet-4-5-20251020",
        temperature=0.8,
        max_tokens=4096,
        streams=True,
    )


@pytest.fixture
def test_model() -> TestModel:
    """pydantic-ai TestModel — replaces real LLM with deterministic responses.

    By default:
    - Calls all tools registered on the agent
    - Returns a valid response matching output_type
    - Makes zero API calls

    Customize with: TestModel(custom_output_text="Your response here")
    """
    return TestModel(custom_output_text="Test response from pydantic-ai TestModel.")


@pytest.fixture
def registry() -> ModelRegistry:
    """ModelRegistry instance for tests."""
    from narrare_core.llm.gateway import ModelRegistry

    return ModelRegistry()


@pytest.fixture
def registry_with_test_model(test_model: TestModel) -> Generator[ModelRegistry]:
    """ModelRegistry wired with TestModel — no real LLM calls.

    Patches the provider registry's ``get`` function to return a factory
    that always produces ``TestModel``, so no API calls are made.
    """
    from unittest.mock import patch

    from narrare_core.llm.gateway import ModelRegistry

    registry = ModelRegistry()
    # Must patch at the point of use (gateway.get_provider), not the source module
    # because "from X import get as get_provider" creates a local binding.
    with patch("narrare_core.llm.gateway.get_provider") as mock_get:
        mock_get.return_value = lambda model_id, **kwargs: test_model
        yield registry


@pytest.fixture
def capture_messages():
    """Context manager that captures all messages exchanged during an agent run.

    Use to assert tool calls, multi-turn conversation flow, and message ordering.
    Requires pydantic-ai >= 1.0.

    Example usage (for future writing session tests with tools):

        from pydantic_ai import Agent
        from pydantic_ai.models.test import TestModel

        agent = Agent('test', output_type=str)

        @agent.tool
        async def lookup_character(ctx, name: str) -> str:
            return f"Character: {name}"

        test_model = TestModel()
        with capture_messages() as messages:
            with agent.override(model=test_model):
                result = await agent.run("Write about Anna")

        tool_calls = [
            part for msg in messages
            for part in msg.parts if hasattr(part, "tool_name")
        ]
        assert any(tc.tool_name == "lookup_character" for tc in tool_calls)
    """
    from pydantic_ai import (  # narrare: allow reason="message capture fixture"
        capture_run_messages,
    )

    return capture_run_messages
