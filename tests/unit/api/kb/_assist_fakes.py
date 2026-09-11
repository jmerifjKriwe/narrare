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

from narrare.kb.context_contracts import KBContextBundle
from narrare_core.agents.kb_assist_agent import KBAssistDeps
from narrare_core.agents.kb_assist_types import KBAssistOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm._prepared_call import PreparedModelCall
from narrare_core.prompts.composer import ComposedPrompt

if TYPE_CHECKING:
    from pydantic_ai.usage import UsageLimits

    from narrare.kb.assist_service import KBAssistService
    from narrare_core.llm.intents import LLMIntent


class FakeModelRegistry:
    """Fake ModelRegistry returning a stub Model.

    ``prepare`` mirrors the real single assembly point (Task 4/6c):
    exactly one ``get_model`` resolution plus a canned sentinel settings
    dict, so pass-through wiring stays assertable.
    """

    def __init__(self) -> None:
        self.get_model: AsyncMock = AsyncMock(return_value=MagicMock(spec=object))
        self.prepare_calls: list[dict[str, object]] = []

    async def prepare(
        self,
        config: ResolvedModelConfig,
        *,
        intent: LLMIntent | None = None,
        usage_limits: UsageLimits | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> PreparedModelCall:
        model = await self.get_model(config, api_key=api_key, base_url=base_url)
        prepared = PreparedModelCall(
            model=model,
            model_settings={"max_tokens": 12_345},
            usage_limits=usage_limits,
        )
        self.prepare_calls.append({"config": config, "intent": intent, "prepared": prepared})
        return prepared


class FakeKBContextProvider:
    """Fake KBContextProviderProtocol for KBAssistService construction.

    Returns a configurable world-context string (empty by default) so the
    canonical ``- name (type): brief`` aggregate is exercised without a DB.
    Mirrors the real provider's RULE-11 contract: ``fetch_world_context``
    returns the configured string and never raises.
    """

    def __init__(self, world_context: str = "") -> None:
        self.fetch_world_context: AsyncMock = AsyncMock(return_value=world_context)
        self.fetch_context: AsyncMock = AsyncMock(return_value=KBContextBundle.empty())
        self.fetch_entities: AsyncMock = AsyncMock(return_value=[])


class FakeComposer:
    """Fake PromptComposer returning a stub ComposedPrompt."""

    def __init__(self) -> None:
        self.build: AsyncMock = AsyncMock(
            return_value=ComposedPrompt(system="Test system prompt.", user="Test user.")
        )


def make_service(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    kb_context_provider: FakeKBContextProvider,
    composer: FakeComposer,
) -> KBAssistService:
    """Build a KBAssistService wired with the standard fakes."""
    from narrare.kb.assist_service import KBAssistService

    return KBAssistService(
        registry=registry,  # type: ignore[arg-type]
        config=config,
        kb_context_provider=kb_context_provider,  # type: ignore[arg-type]
        prompt_composer=composer,  # type: ignore[arg-type]
    )


__all__ = [
    "FakeComposer",
    "FakeKBContextProvider",
    "FakeModelRegistry",
    "KBAssistDeps",
    "KBAssistOutput",
    "ResolvedModelConfig",
    "make_service",
]
