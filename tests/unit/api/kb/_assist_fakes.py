"""Shared fakes and helpers for KBAssistService tests (RULE-04 split).

Provides Fake classes and the ``make_service`` factory so that
``test_assist_service.py`` and ``test_assist_service_fallback.py`` can
both construct a wired ``KBAssistService`` without duplicating the
fake-collaborator definitions (RULE-TEST-01: typed Fake classes, no
bare MagicMock for domain contracts).

Pytest fixtures live in ``conftest.py`` (one level up) so they are
discoverable from both test modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

from narrare_core.agents.kb_assist_agent import KBAssistDeps
from narrare_core.agents.kb_assist_types import KBAssistOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from narrare.kb.assist_service import KBAssistService


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model."""

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))


class FakeProactiveContext:
    """Fake ProactiveContextProtocol for KBAssistService construction."""

    def __init__(self) -> None:
        self.suggest: AsyncMock = AsyncMock(return_value=[])


class FakeComposer:
    """Fake PromptComposer returning a stub ComposedPrompt."""

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="Test system prompt.", user="Test user.")
        )


def make_service(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    proactive_context: FakeProactiveContext,
    composer: FakeComposer,
) -> KBAssistService:
    """Build a KBAssistService wired with the standard fakes."""
    from narrare.kb.assist_service import KBAssistService

    return KBAssistService(
        registry=registry,  # type: ignore[arg-type]
        config=config,
        proactive_context=proactive_context,  # type: ignore[arg-type]
        prompt_composer=composer,  # type: ignore[arg-type]
    )


__all__ = [
    "FakeComposer",
    "FakeModelRegistry",
    "FakeProactiveContext",
    "KBAssistDeps",
    "KBAssistOutput",
    "ResolvedModelConfig",
    "make_service",
]
