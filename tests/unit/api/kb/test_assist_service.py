"""Unit tests for KBAssistService — invocation composition (ADR-048 Mode 1).

Verifies that ``_run_agent`` routes through ``compose_invocation`` with the
correct Mode 1 (composer-driven) parameters, so enrichment flows through
the composer into the system prompt.

Fallback-path tests live in ``test_assist_service_fallback.py`` (RULE-04
split, AUFG-03-02).

See:
    ADR-048, ADR-045 Decision 7,
    CONSTRAINTS.md RULE-02a/RULE-03/RULE-11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from narrare._app.dependencies_services import StaticModelResolution
from narrare.kb.assist_service import KBAssistService
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.model_routing import ResolvedModel

if TYPE_CHECKING:
    from narrare_core.agents.kb_assist_agent import KBAssistDeps
    from narrare_core.agents.kb_assist_types import KBAssistOutput
    from narrare_core.llm import ResolvedModelConfig

    from ._assist_fakes import (
        FakeComposer,
        FakeKBContextProvider,
        FakeModelRegistry,
    )

# ---------------------------------------------------------------------------
# Invocation composition — ADR-048 Mode 1 (composer-driven)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_agent_calls_compose_invocation_mode1(
    config: ResolvedModelConfig,
    registry: FakeModelRegistry,
    kb_context_provider: FakeKBContextProvider,
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
        model_resolution=StaticModelResolution(ResolvedModel(config=config)),
        kb_context_provider=kb_context_provider,  # type: ignore[arg-type]
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


# ---------------------------------------------------------------------------
# World context — KBContextProvider is the single source (ADR-067)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_deps_sources_world_context_via_provider(
    kb_context_provider: FakeKBContextProvider,
) -> None:
    """build_assist_deps obtains world_context from KBContextProvider (ADR-067).

    Consolidates the former inline ``proactive_context.suggest`` + relevance
    formatting: assist now routes through the canonical KBContextProvider so
    kb assist/improve share one world-context source. Verifies the provider is
    called with the novel id + entity type and that the rendered ``- name
    (type): brief`` string flows into ``deps.world_context``.
    """
    from uuid import uuid4

    from narrare.kb._assist_context import build_assist_deps

    canonical_context = "- Alice (character): A brave hero"

    # Configure the canonical wire format the provider renders.
    kb_context_provider.fetch_world_context = AsyncMock(return_value=canonical_context)

    novel_id = uuid4()
    deps = await build_assist_deps(
        kb_context_provider,  # type: ignore[arg-type]
        novel_id=novel_id,
        entity_type="character",
        existing_fields={"name": "Bob"},
    )

    kb_context_provider.fetch_world_context.assert_awaited_once()
    call_kwargs = kb_context_provider.fetch_world_context.call_args
    assert call_kwargs.args[0] == novel_id
    assert call_kwargs.kwargs["entity_type"] == "character"
    # The canonical aggregate flows straight into deps (single source).
    assert deps.world_context == canonical_context
