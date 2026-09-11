"""Tests for CoreferenceAgent — instantiation and validation.

The strict output validator (ADR-035) invariants are tested directly.
No real LLM calls (RULE-01b). Type/deps tests live in
test_coreference_types.py.
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.coreference_agent import CoreferenceAgent
from narrare_core.agents.coreference_types import (
    CoreferenceDeps,
    CoreferenceOutput,
    PronounResolution,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> CoreferenceAgent:
    return CoreferenceAgent(model=TestModel())


def _make_ctx(deps: CoreferenceDeps | None = None) -> RunContext[CoreferenceDeps]:
    return RunContext[CoreferenceDeps](
        deps=deps or CoreferenceDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


@pytest.fixture()
def ctx() -> RunContext[CoreferenceDeps]:
    return _make_ctx()


# ---------------------------------------------------------------------------
# C. Instantiation
# ---------------------------------------------------------------------------


class TestCoreferenceAgentInstantiation:
    """CoreferenceAgent instantiates correctly."""

    def test_can_be_instantiated(self) -> None:
        agent = CoreferenceAgent(model=TestModel())
        assert isinstance(agent, CoreferenceAgent)

    def test_instantiated_with_system_prompt(self) -> None:
        agent = CoreferenceAgent(
            model=TestModel(),
            system_prompt="You are a coreference analyst.",
        )
        assert isinstance(agent, CoreferenceAgent)


# ---------------------------------------------------------------------------
# F. Validation invariants (_validate_output)
# ---------------------------------------------------------------------------


class TestCoreferenceAgentValidation:
    """_validate_output enforces deterministic invariants (ADR-035)."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: CoreferenceAgent, ctx: RunContext[CoreferenceDeps]
    ) -> None:
        output = CoreferenceOutput(
            summary="Clear passage.",
            resolutions=[
                PronounResolution(pronoun="She", referent="Alice", confidence=0.9),
            ],
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.resolutions) == 1

    @pytest.mark.asyncio
    async def test_empty_summary_triggers_model_retry(
        self, agent: CoreferenceAgent, ctx: RunContext[CoreferenceDeps]
    ) -> None:
        """An empty summary raises ModelRetry (every analysis needs assessment)."""
        with pytest.raises(ModelRetry):
            await agent._validate_output(ctx, CoreferenceOutput(summary=""))

    @pytest.mark.asyncio
    async def test_whitespace_summary_triggers_model_retry(
        self, agent: CoreferenceAgent, ctx: RunContext[CoreferenceDeps]
    ) -> None:
        """A whitespace-only summary raises ModelRetry."""
        with pytest.raises(ModelRetry):
            await agent._validate_output(ctx, CoreferenceOutput(summary="   \n  "))

    @pytest.mark.asyncio
    async def test_empty_pronoun_resolutions_filtered(
        self, agent: CoreferenceAgent, ctx: RunContext[CoreferenceDeps]
    ) -> None:
        """Resolutions with an empty pronoun token are filtered out."""
        output = CoreferenceOutput(
            summary="Clear passage.",
            resolutions=[
                PronounResolution(pronoun="She", referent="Alice", confidence=0.9),
                PronounResolution(pronoun="", referent="Bob", confidence=0.5),
                PronounResolution(pronoun="  ", referent="Bob", confidence=0.5),
            ],
        )
        validated = await agent._validate_output(ctx, output)
        assert len(validated.resolutions) == 1
        assert validated.resolutions[0].pronoun == "She"

    @pytest.mark.asyncio
    async def test_empty_resolutions_with_summary_passes(
        self, agent: CoreferenceAgent, ctx: RunContext[CoreferenceDeps]
    ) -> None:
        """An empty resolutions list with a non-empty summary is valid."""
        output = CoreferenceOutput(summary="No pronouns found in this passage.")
        result = await agent._validate_output(ctx, output)
        assert result.resolutions == []
