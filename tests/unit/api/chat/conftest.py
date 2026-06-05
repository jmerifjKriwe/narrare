"""Shared fixtures and helpers for ChatService unit tests."""

# pyright: reportUnusedFunction=false

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare_core.agents.base import StreamEvent

from narrare_core.chat.contracts import ChatRequest

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


async def _async_gen(*events: StreamEvent) -> AsyncIterator[StreamEvent]:
    """Turn StreamEvent instances into an async generator.

    Use this to simulate ``ChatAgent.run_stream()`` return values in tests.
    """
    for event in events:
        yield event


def _make_mock_composer() -> AsyncMock:
    """Create a mock PromptComposer that returns a known ComposedPrompt."""
    from narrare_core.prompts.composer import ComposedPrompt

    composer = AsyncMock()
    composer.build = AsyncMock(
        return_value=ComposedPrompt(
            system="You are a helpful writing assistant.",
            user="Hello!",
        )
    )
    return composer


def _make_mock_registry() -> AsyncMock:
    """Create a mock ModelRegistry."""
    registry = AsyncMock()
    registry.get_model = AsyncMock()
    return registry


def _make_config() -> MagicMock:
    """Create a mock ResolvedModelConfig."""
    from narrare_core.llm import ResolvedModelConfig

    config = MagicMock(spec=ResolvedModelConfig)
    config.provider_name = "anthropic"
    config.model_id = "claude-sonnet-4-5-20251020"
    return config


def _make_request(
    message: str = "Hello!",
    conversation_id: UUID | None = None,
) -> ChatRequest:
    """Create a ChatRequest with sensible defaults."""
    from uuid import uuid4

    return ChatRequest(
        project_id=uuid4(),
        message=message,
        conversation_id=conversation_id,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_composer() -> AsyncMock:
    return _make_mock_composer()


@pytest.fixture
def mock_registry() -> AsyncMock:
    return _make_mock_registry()


@pytest.fixture
def mock_config() -> MagicMock:
    return _make_config()


@pytest.fixture
def in_memory_store():
    """InMemoryConversationStore — no DB needed for unit tests."""
    from narrare_core.chat.conversation_store import InMemoryConversationStore

    return InMemoryConversationStore()


@pytest.fixture
def service(
    mock_composer: AsyncMock,
    mock_registry: AsyncMock,
    in_memory_store: MagicMock,
    mock_config: MagicMock,
) -> object:
    """Create a ``ChatService`` with fully mocked dependencies."""
    from narrare.chat.chat_service import ChatService

    return ChatService(
        prompt_composer=mock_composer,
        model_registry=mock_registry,
        conversation_store=in_memory_store,
        config=mock_config,
    )
