"""Tests for TimelineAgent output validator — ADR-035.

Tests the deterministic invariants enforced by _validate_output:
- Each event must have non-empty event_name and description
- chapter_reference non-empty for each event (traceability)
- No duplicate events (same event_name + timestamp)
- Filter out events with empty event_name

Test strategy:
- Call _validate_output directly with mocked RunContext
- No real LLM calls (RULE-01)
"""

from __future__ import annotations

import pytest
from pydantic_ai import ModelRetry, RunContext, RunUsage
from pydantic_ai.models.test import TestModel

from narrare_core.agents.timeline_agent import TimelineAgent, TimelineDeps
from narrare_core.agents.timeline_types import TimelineEvent, TimelineOutput

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> TimelineAgent:
    return TimelineAgent(model=TestModel())


@pytest.fixture()
def ctx() -> RunContext[TimelineDeps]:
    return RunContext[TimelineDeps](
        deps=TimelineDeps(),
        model=TestModel(),
        usage=RunUsage(),
    )


def _make_event(**overrides: object) -> TimelineEvent:
    """Build a valid TimelineEvent for testing."""
    defaults: dict[str, object] = {
        "event_name": "The Crossing",
        "description": "Elena crosses the Silver Bridge at dawn.",
        "timestamp": "Day 15, morning",
        "chapter_reference": "Chapter 5",
        "characters_involved": ["Elena", "Marcus"],
        "location": "Silver Bridge",
    }
    defaults.update(overrides)
    return TimelineEvent(**defaults)  # type: ignore[arg-type]


def _valid_output(**event_overrides: object) -> TimelineOutput:
    """Build a valid TimelineOutput for testing."""
    return TimelineOutput(timeline_events=[_make_event(**event_overrides)])


# ---------------------------------------------------------------------------
# A. Valid output passes through
# ---------------------------------------------------------------------------


class TestValidOutputPasses:
    """Valid output passes the validator unchanged."""

    @pytest.mark.asyncio
    async def test_valid_event_passes(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = _valid_output()
        result = await agent._validate_output(ctx, output)
        assert len(result.timeline_events) == 1
        assert result.timeline_events[0].event_name == "The Crossing"

    @pytest.mark.asyncio
    async def test_multiple_valid_events(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(event_name="Event A", timestamp="Day 1"),
                _make_event(event_name="Event B", timestamp="Day 2"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.timeline_events) == 2

    @pytest.mark.asyncio
    async def test_empty_events_list_passes(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput()
        result = await agent._validate_output(ctx, output)
        assert result.timeline_events == []


# ---------------------------------------------------------------------------
# B. Filter empty-name events
# ---------------------------------------------------------------------------


class TestFilterEmptyNames:
    """Events with empty event_names are silently filtered out."""

    @pytest.mark.asyncio
    async def test_empty_name_filtered(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(event_name=""),
                _make_event(event_name="The Crossing"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.timeline_events) == 1
        assert result.timeline_events[0].event_name == "The Crossing"

    @pytest.mark.asyncio
    async def test_whitespace_name_filtered(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(event_name="   "),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert result.timeline_events == []


# ---------------------------------------------------------------------------
# C. Invariant violations — ModelRetry
# ---------------------------------------------------------------------------


class TestInvariantViolations:
    """Invariant violations raise ModelRetry with helpful messages."""

    @pytest.mark.asyncio
    async def test_empty_description_raises(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(description=""),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty description"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_description_raises(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(description="   "),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty description"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_empty_chapter_reference_raises(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(chapter_reference=""),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty chapter_reference"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_whitespace_chapter_reference_raises(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(chapter_reference="   "),
            ]
        )
        with pytest.raises(ModelRetry, match="non-empty chapter_reference"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_duplicate_events_raises(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(event_name="The Crossing", timestamp="Day 15"),
                _make_event(event_name="The Crossing", timestamp="Day 15"),
            ]
        )
        with pytest.raises(ModelRetry, match="Duplicate timeline event"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_same_name_different_timestamp_passes(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        """Same event_name but different timestamps are NOT duplicates."""
        output = TimelineOutput(
            timeline_events=[
                _make_event(event_name="The Crossing", timestamp="Day 15"),
                _make_event(event_name="The Crossing", timestamp="Day 42"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.timeline_events) == 2

    @pytest.mark.asyncio
    async def test_same_timestamp_different_name_passes(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        """Different event_names with same timestamp are NOT duplicates."""
        output = TimelineOutput(
            timeline_events=[
                _make_event(event_name="The Crossing", timestamp="Day 15"),
                _make_event(event_name="The Ambush", timestamp="Day 15"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.timeline_events) == 2


# ---------------------------------------------------------------------------
# D. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_mixed_valid_and_empty_name_events(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(event_name=""),
                _make_event(event_name="Event A"),
                _make_event(event_name="   "),
                _make_event(event_name="Event B"),
            ]
        )
        result = await agent._validate_output(ctx, output)
        assert len(result.timeline_events) == 2
        assert result.timeline_events[0].event_name == "Event A"
        assert result.timeline_events[1].event_name == "Event B"

    @pytest.mark.asyncio
    async def test_empty_timestamp_not_considered_duplicate(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        """Two events with same name and empty timestamp ARE duplicates."""
        output = TimelineOutput(
            timeline_events=[
                _make_event(event_name="The Crossing", timestamp=""),
                _make_event(event_name="The Crossing", timestamp=""),
            ]
        )
        with pytest.raises(ModelRetry, match="Duplicate timeline event"):
            await agent._validate_output(ctx, output)

    @pytest.mark.asyncio
    async def test_event_with_minimal_fields(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        """An event with only required fields passes."""
        event = TimelineEvent(
            event_name="The Crossing",
            description="Something happens.",
            chapter_reference="Chapter 1",
        )
        output = TimelineOutput(timeline_events=[event])
        result = await agent._validate_output(ctx, output)
        assert len(result.timeline_events) == 1


# ---------------------------------------------------------------------------
# E. Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same input always produces same validation result."""

    @pytest.mark.asyncio
    async def test_deterministic_pass(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = _valid_output()
        result1 = await agent._validate_output(ctx, output)
        result2 = await agent._validate_output(ctx, output)
        assert len(result1.timeline_events) == len(result2.timeline_events)
        assert result1.timeline_events[0].event_name == result2.timeline_events[0].event_name

    @pytest.mark.asyncio
    async def test_deterministic_retry(
        self, agent: TimelineAgent, ctx: RunContext[TimelineDeps]
    ) -> None:
        output = TimelineOutput(
            timeline_events=[
                _make_event(description=""),
            ]
        )
        for _ in range(3):
            with pytest.raises(ModelRetry, match="non-empty description"):
                await agent._validate_output(ctx, output)
