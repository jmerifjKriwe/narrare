"""Shared fixtures for core/llm/ unit tests.

Provides pydantic-ai testing tools (TestModel, FunctionModel) for tests
that exercise the gateway->agent bridge. These replace hand-rolled fakes
with pydantic-ai's built-in test models, which stay in sync with the
library automatically.

See: docs/development/testing-standards.md — RULE-TEST-01
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai.models.test import (  # narrare: allow
    TestModel,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from narrare_core.llm.gateway import LLMGateway


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
def gateway_with_test_model(test_model: TestModel) -> Generator[LLMGateway]:
    """LLMGateway wired with TestModel — no FakePydanticAgent needed.

    The gateway's _make_agent still creates real pydantic-ai Agents,
    but the model is TestModel so no API calls are made. Only
    _get_model_with_credentials is patched to inject TestModel.
    """
    from unittest.mock import patch

    from narrare_core.llm.gateway import LLMGateway

    gateway = LLMGateway(default_provider="anthropic")

    with patch.object(gateway, "_get_model_with_credentials", return_value=test_model):
        yield gateway


@pytest.fixture
def capture_messages():
    """Context manager that captures all messages exchanged during an agent run.

    Use to assert tool calls, multi-turn conversation flow, and message ordering.
    Requires pydantic-ai >= 1.0.
    """
    from pydantic_ai import (  # narrare: allow
        capture_run_messages,
    )

    return capture_run_messages
