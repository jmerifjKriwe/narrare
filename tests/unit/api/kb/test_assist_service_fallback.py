"""Fallback-path tests for KBAssistService._run_agent (AUFG-03-02).

Split from ``test_assist_service.py`` to respect RULE-04. Covers the
hardened fallback contract:

- Typed exceptions (``InvocationValidationError``, ``PromptError``) trigger
  graceful degradation (composer.build fallback).
- ``composed_prompt is None`` raises ``ConfigurationError`` (replaces the
  prior runtime ``assert``) and flows into the fallback.
- Generic exceptions (e.g. ``RuntimeError``) propagate fail-fast — the
  narrowed handler does NOT catch broad ``Exception``.

See: AUFG-03-02 in
``_audit/results/technical-review/review-03-ai-features.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare_core.agents.kb_assist_types import KBAssistOutput
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare_core.llm import ResolvedModelConfig

from ._assist_fakes import (
    FakeComposer,
    FakeKBContextProvider,
    FakeModelRegistry,
    make_service,
)


@pytest.mark.asyncio
async def test_invocation_validation_error_triggers_fallback(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    kb_context_provider: FakeKBContextProvider,
    composer: FakeComposer,
    deps: object,
    agent_output: KBAssistOutput,
) -> None:
    """InvocationValidationError is caught and the agent still runs.

    The narrowed handler accepts documented composition-failure modes
    (InvocationValidationError, PromptError, ConfigurationError) and
    falls back to direct composer.build() so the agent still runs.
    """
    from narrare_core.shared.errors import InvocationValidationError

    service = make_service(config, registry, kb_context_provider, composer)

    with (
        patch("narrare.kb.assist_service.KBAssistAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(
                side_effect=InvocationValidationError(
                    "validation failed", code="INVOCATION_VALIDATION_FAILED"
                )
            ),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=agent_output)
        MockAgent.return_value = mock_agent

        result = await service._run_agent(
            user_prompt="Ask the next question.",
            deps=deps,  # type: ignore[arg-type]
            intent=LLMIntent.KB_INTERVIEW,
            entity_type="character",
            existing_fields={},
        )

    assert composer.build.await_count == 1
    assert result is agent_output


@pytest.mark.asyncio
async def test_prompt_error_triggers_fallback(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    kb_context_provider: FakeKBContextProvider,
    composer: FakeComposer,
    deps: object,
    agent_output: KBAssistOutput,
) -> None:
    """PromptError subclasses are also recoverable."""
    from narrare_core.shared.errors import PromptVariableError

    service = make_service(config, registry, kb_context_provider, composer)

    with (
        patch("narrare.kb.assist_service.KBAssistAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(side_effect=PromptVariableError(variable="world_context")),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=agent_output)
        MockAgent.return_value = mock_agent

        result = await service._run_agent(
            user_prompt="Ask the next question.",
            deps=deps,  # type: ignore[arg-type]
            intent=LLMIntent.KB_INTERVIEW,
            entity_type="character",
            existing_fields={},
        )

    assert composer.build.await_count == 1
    assert result is agent_output


@pytest.mark.asyncio
async def test_unexpected_exception_propagates(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    kb_context_provider: FakeKBContextProvider,
    composer: FakeComposer,
    deps: object,
) -> None:
    """Non-composition exceptions propagate (no broad except Exception).

    A generic RuntimeError indicates a genuine pipeline fault; the
    narrowed handler must let it surface fail-fast.
    """
    service = make_service(config, registry, kb_context_provider, composer)

    with (
        patch("narrare.kb.assist_service.KBAssistAgent"),
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(side_effect=RuntimeError("genuine pipeline fault")),
        ),
        pytest.raises(RuntimeError, match="genuine pipeline fault"),
    ):
        await service._run_agent(
            user_prompt="Ask the next question.",
            deps=deps,  # type: ignore[arg-type]
            intent=LLMIntent.KB_INTERVIEW,
            entity_type="character",
            existing_fields={},
        )

    assert composer.build.await_count == 0


@pytest.mark.asyncio
async def test_composition_none_raises_configuration_error(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    kb_context_provider: FakeKBContextProvider,
    composer: FakeComposer,
    deps: object,
) -> None:
    """composed_prompt=None is a typed ConfigurationError, not an assert.

    The ConfigurationError flows into the narrowed handler and triggers
    the documented fallback; no error escapes the service.
    """
    service = make_service(config, registry, kb_context_provider, composer)

    fake_result = MagicMock(spec=["composed_prompt"])
    fake_result.composed_prompt = None
    agent_output = MagicMock(spec=KBAssistOutput)

    with (
        patch("narrare.kb.assist_service.KBAssistAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(return_value=fake_result),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=agent_output)
        MockAgent.return_value = mock_agent

        result = await service._run_agent(
            user_prompt="Ask the next question.",
            deps=deps,  # type: ignore[arg-type]
            intent=LLMIntent.KB_INTERVIEW,
            entity_type="character",
            existing_fields={},
        )

    assert composer.build.await_count == 1
    assert result is agent_output
