"""Unit tests for KBAssistService — invocation composition (ADR-048 Mode 1).

Verifies that ``_run_agent`` routes through ``compose_invocation`` with the
correct Mode 1 (composer-driven) parameters, so enrichment flows through
the composer into the system prompt.

See:
    ADR-048, ADR-045 Decision 7,
    CONSTRAINTS.md RULE-02a/RULE-03/RULE-11.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare.kb.assist_service import KBAssistService
from narrare_core.agents.kb_assist_agent import KBAssistDeps
from narrare_core.agents.kb_assist_types import KBAssistOutput
from narrare_core.llm import ResolvedModelConfig
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.composer import ComposedPrompt

# ---------------------------------------------------------------------------
# Fake dependency classes (avoid bare MagicMock for domain contracts — RULE-TEST-01)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_name="test", model_id="test-model", temperature=0.7, max_tokens=4096
    )


@pytest.fixture
def registry() -> FakeModelRegistry:
    return FakeModelRegistry()


@pytest.fixture
def proactive_context() -> FakeProactiveContext:
    return FakeProactiveContext()


@pytest.fixture
def composer() -> FakeComposer:
    return FakeComposer()


@pytest.fixture
def deps() -> KBAssistDeps:
    return KBAssistDeps(
        language="en",
        entity_type="character",
        template_structure={"name": "Name"},
    )


@pytest.fixture
def agent_output() -> KBAssistOutput:
    return KBAssistOutput(
        mode="question",
        question="What is the character's name?",
        field_key="name",
    )


# ---------------------------------------------------------------------------
# Invocation composition — ADR-048 Mode 2 (agent-internal)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_calls_compose_invocation_mode1(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    proactive_context: FakeProactiveContext,
    composer: FakeComposer,
    deps: KBAssistDeps,
    agent_output: KBAssistOutput,
) -> None:
    """_run_agent routes through compose_invocation (Mode 1) per ADR-048.

    Enrichment flows through the composer into the system prompt. The
    service must call compose_invocation with the composer (not
    manual_injection) and the kb_assist feature_id.
    """
    service = KBAssistService(
        registry=registry,  # type: ignore[arg-type]
        config=config,
        proactive_context=proactive_context,  # type: ignore[arg-type]
        prompt_composer=composer,  # type: ignore[arg-type]
    )

    with (
        patch("narrare.kb.assist_service.KBAssistAgent") as MockAgent,
        patch("narrare_core.ai_invocation.compose_invocation", new=AsyncMock()) as mock_compose,
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=agent_output)
        MockAgent.return_value = mock_agent

        result = await service._run_agent(
            user_prompt="Ask the next question.",
            deps=deps,
            intent=LLMIntent.KB_INTERVIEW,
            entity_type="character",
            existing_fields={},
        )

    mock_compose.assert_awaited_once()
    kwargs = mock_compose.call_args.kwargs
    assert kwargs.get("composer") is not None  # Mode 1 — composer-driven
    assert "manual_injection" not in kwargs  # Not Mode 2
    assert kwargs["invocation_context"].feature_id == "kb_assist"
    assert result is agent_output


@pytest.mark.asyncio
async def test_run_agent_compose_invocation_failure_is_graceful(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    proactive_context: FakeProactiveContext,
    composer: FakeComposer,
    deps: KBAssistDeps,
    agent_output: KBAssistOutput,
) -> None:
    """compose_invocation failure is caught and logged (RULE-11), agent still runs."""
    service = KBAssistService(
        registry=registry,  # type: ignore[arg-type]
        config=config,
        proactive_context=proactive_context,  # type: ignore[arg-type]
        prompt_composer=composer,  # type: ignore[arg-type]
    )

    with (
        patch("narrare.kb.assist_service.KBAssistAgent") as MockAgent,
        patch(
            "narrare_core.ai_invocation.compose_invocation",
            new=AsyncMock(side_effect=RuntimeError("pipeline offline")),
        ),
    ):
        mock_agent = MagicMock(spec=["run"])
        mock_agent.run = AsyncMock(return_value=agent_output)
        MockAgent.return_value = mock_agent

        # Must not raise — failure is logged, not propagated.
        result = await service._run_agent(
            user_prompt="Ask the next question.",
            deps=deps,
            intent=LLMIntent.KB_INTERVIEW,
            entity_type="character",
            existing_fields={},
        )

    assert result is agent_output
