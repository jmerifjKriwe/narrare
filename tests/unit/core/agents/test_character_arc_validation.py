"""Tests for CharacterArcAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- character_name must be non-empty
- phases should have 3-5 entries when present
- Each phase should have non-empty phase_name and description
- starting_state and ending_state should be non-empty

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.character_arc_agent import CharacterArcAgent, CharacterArcDeps
from narrare_core.agents.character_arc_types import ArcPhase, CharacterArcOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> CharacterArcAgent:
    return CharacterArcAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[CharacterArcDeps]:
    return RunContext[CharacterArcDeps](
        deps=CharacterArcDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_phase(**overrides: object) -> ArcPhase:
    """Build a valid ArcPhase for testing."""
    defaults: dict[str, object] = {
        "phase_name": "Inciting Incident",
        "description": "The hero discovers the truth.",
        "emotional_state": "Shocked",
    }
    defaults.update(overrides)
    return ArcPhase(**defaults)  # type: ignore[arg-type]


def _valid_output(**overrides: object) -> CharacterArcOutput:
    """Build a valid CharacterArcOutput for testing."""
    defaults: dict[str, object] = {
        "character_name": "Lyra",
        "starting_state": "A timid orphan",
        "ending_state": "A confident leader",
        "phases": [
            _make_phase(phase_name="Call to Adventure", description="Lyra finds the compass."),
            _make_phase(phase_name="Trials", description="Lyra faces challenges."),
            _make_phase(phase_name="Transformation", description="Lyra finds inner strength."),
        ],
    }
    defaults.update(overrides)
    return CharacterArcOutput(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_output_passes(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert result.character_name == "Lyra"
        assert len(result.phases) == 3

    @pytest.mark.asyncio
    async def test_valid_with_four_phases(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        phases = [_make_phase(phase_name=f"Phase {i}", description=f"Desc {i}") for i in range(4)]
        output = _valid_output(phases=phases)
        result = await agent._validate_output(ctx, output)
        assert len(result.phases) == 4

    @pytest.mark.asyncio
    async def test_valid_with_five_phases(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        phases = [_make_phase(phase_name=f"Phase {i}", description=f"Desc {i}") for i in range(5)]
        output = _valid_output(phases=phases)
        result = await agent._validate_output(ctx, output)
        assert len(result.phases) == 5

    @pytest.mark.asyncio
    async def test_valid_with_no_phases(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        """Empty phases list is valid (no phases present)."""
        output = _valid_output(phases=[])
        result = await agent._validate_output(ctx, output)
        assert result.phases == []


# ---------------------------------------------------------------------------
# B. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_empty_character_name_raises(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        output = _valid_output(character_name="")
        with pytest.raises(ModelRetry, match="character_name"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_character_name_raises(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        output = _valid_output(character_name="   ")
        with pytest.raises(ModelRetry, match="character_name"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_empty_starting_state_raises(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        output = _valid_output(starting_state="")
        with pytest.raises(ModelRetry, match="starting_state"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_empty_ending_state_raises(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        output = _valid_output(ending_state="")
        with pytest.raises(ModelRetry, match="ending_state"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_too_few_phases_raises(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        phases = [
            _make_phase(phase_name="Phase 1", description="Desc 1"),
            _make_phase(phase_name="Phase 2", description="Desc 2"),
        ]
        output = _valid_output(phases=phases)
        with pytest.raises(ModelRetry, match="3-5"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_too_many_phases_raises(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        phases = [_make_phase(phase_name=f"P{i}", description=f"D{i}") for i in range(6)]
        output = _valid_output(phases=phases)
        with pytest.raises(ModelRetry, match="3-5"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_phase_empty_name_raises(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        phases = [
            _make_phase(phase_name="", description="Valid desc"),
            _make_phase(phase_name="Valid", description="Valid"),
            _make_phase(phase_name="Valid2", description="Valid2"),
        ]
        output = _valid_output(phases=phases)
        with pytest.raises(ModelRetry, match="empty phase_name"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_phase_empty_description_raises(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        phases = [
            _make_phase(phase_name="Valid", description=""),
            _make_phase(phase_name="Valid2", description="Valid2"),
            _make_phase(phase_name="Valid3", description="Valid3"),
        ]
        output = _valid_output(phases=phases)
        with pytest.raises(ModelRetry, match="empty description"):
            await agent._validate_output(ctx, output)


# ---------------------------------------------------------------------------
# C. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_exactly_three_phases_passes(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        phases = [_make_phase(phase_name=f"P{i}", description=f"D{i}") for i in range(3)]
        output = _valid_output(phases=phases)
        result = await agent._validate_output(ctx, output)
        assert len(result.phases) == 3

    @pytest.mark.asyncio
    async def test_exactly_five_phases_passes(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        phases = [_make_phase(phase_name=f"P{i}", description=f"D{i}") for i in range(5)]
        output = _valid_output(phases=phases)
        result = await agent._validate_output(ctx, output)
        assert len(result.phases) == 5


# ---------------------------------------------------------------------------
# D. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert result1.character_name == result2.character_name

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: CharacterArcAgent, ctx: RunContext[CharacterArcDeps]
    ) -> None:
        output = _valid_output(character_name="")
        for _ in range(3):
            with pytest.raises(ModelRetry, match="character_name"):
                await agent._validate_output(ctx, output)
