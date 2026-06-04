"""Tests for HistoryPolicy enum and NarrareAgent integration (ADR-034)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai.models.test import TestModel

from narrare_core.agents import HistoryPolicy, NarrareAgent

if TYPE_CHECKING:
    from pydantic_ai.models import Model


class TestHistoryPolicyEnum:
    """Tests for the HistoryPolicy enum itself."""

    def test_has_none_value(self) -> None:
        """HistoryPolicy.NONE exists with value 'none'."""
        assert HistoryPolicy.NONE.value == "none"

    def test_has_conversational_value(self) -> None:
        """HistoryPolicy.CONVERSATIONAL exists with value 'conversational'."""
        assert HistoryPolicy.CONVERSATIONAL.value == "conversational"

    def test_enum_has_exactly_two_members(self) -> None:
        """HistoryPolicy has exactly NONE and CONVERSATIONAL."""
        members = list(HistoryPolicy)
        assert len(members) == 2
        assert HistoryPolicy.NONE in members
        assert HistoryPolicy.CONVERSATIONAL in members


class TestNarrareAgentHistoryPolicyDefault:
    """Tests that NarrareAgent defaults to HistoryPolicy.NONE."""

    async def test_default_is_none(self) -> None:
        """Agent without explicit history_policy defaults to NONE."""

        class DummyAgent(NarrareAgent[None, str]):
            pass

        agent = DummyAgent(model=TestModel(), deps_type=type(None), output_type=str)
        assert agent.history_policy == HistoryPolicy.NONE

    async def test_default_agent_runs_correctly(self) -> None:
        """Default history_policy does not affect agent execution."""

        class DummyAgent(NarrareAgent[None, str]):
            pass

        agent = DummyAgent(model=TestModel(), deps_type=type(None), output_type=str)
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"


class TestNarrareAgentHistoryPolicyExplicit:
    """Tests that NarrareAgent accepts an explicit history_policy."""

    async def test_conversational_policy_is_stored(self) -> None:
        """Agent with history_policy=CONVERSATIONAL stores it correctly."""

        class DummyAgent(NarrareAgent[None, str]):
            pass

        agent = DummyAgent(
            model=TestModel(),
            deps_type=type(None),
            output_type=str,
            history_policy=HistoryPolicy.CONVERSATIONAL,
        )
        assert agent.history_policy == HistoryPolicy.CONVERSATIONAL

    async def test_explicit_none_policy(self) -> None:
        """Agent with explicit history_policy=NONE stores it correctly."""

        class DummyAgent(NarrareAgent[None, str]):
            pass

        agent = DummyAgent(
            model=TestModel(),
            deps_type=type(None),
            output_type=str,
            history_policy=HistoryPolicy.NONE,
        )
        assert agent.history_policy == HistoryPolicy.NONE

    async def test_conversational_agent_runs_correctly(self) -> None:
        """Agent with CONVERSATIONAL policy still runs normally."""

        class DummyAgent(NarrareAgent[None, str]):
            pass

        agent = DummyAgent(
            model=TestModel(),
            deps_type=type(None),
            output_type=str,
            history_policy=HistoryPolicy.CONVERSATIONAL,
        )
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"


class TestNarrareAgentHistoryPolicyProperty:
    """Tests that history_policy is a read-only property."""

    async def test_property_is_read_only(self) -> None:
        """history_policy property has no setter — assignment raises AttributeError."""

        class DummyAgent(NarrareAgent[None, str]):
            pass

        agent = DummyAgent(model=TestModel(), deps_type=type(None), output_type=str)

        try:
            agent.history_policy = HistoryPolicy.CONVERSATIONAL  # type: ignore[misc]
        except AttributeError:
            pass  # expected — property is read-only
        else:
            raise AssertionError("history_policy should be read-only")

    def test_property_type_annotation(self) -> None:
        """history_policy property returns HistoryPolicy type."""
        # Verify the property descriptor exists and has the correct type
        prop = NarrareAgent.__dict__.get("history_policy")
        assert prop is not None
        assert isinstance(prop, property)


class TestHistoryPolicyBackwardCompatibility:
    """Tests that adding history_policy does not break existing agent patterns."""

    async def test_subclass_with_custom_init_still_works(self) -> None:
        """Agents that override __init__ and call super() still get NONE default."""

        class CustomAgent(NarrareAgent[None, str]):
            def __init__(self, model: Model[Any]) -> None:
                super().__init__(
                    model=model,
                    deps_type=type(None),
                    output_type=str,
                )

        agent = CustomAgent(model=TestModel())
        assert agent.history_policy == HistoryPolicy.NONE
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"

    async def test_agent_with_all_params(self) -> None:
        """Agent with every parameter specified works correctly."""

        class FullAgent(NarrareAgent[None, str]):
            pass

        agent = FullAgent(
            model=TestModel(),
            deps_type=type(None),
            output_type=str,
            system_prompt="You are a test agent.",
            capabilities=[],
            history_policy=HistoryPolicy.CONVERSATIONAL,
        )
        assert agent.history_policy == HistoryPolicy.CONVERSATIONAL
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"

    async def test_different_agents_have_independent_policies(self) -> None:
        """Two agent instances can have different history policies."""

        class AgentA(NarrareAgent[None, str]):
            pass

        class AgentB(NarrareAgent[None, str]):
            pass

        a = AgentA(
            model=TestModel(),
            deps_type=type(None),
            output_type=str,
            history_policy=HistoryPolicy.NONE,
        )
        b = AgentB(
            model=TestModel(),
            deps_type=type(None),
            output_type=str,
            history_policy=HistoryPolicy.CONVERSATIONAL,
        )
        assert a.history_policy == HistoryPolicy.NONE
        assert b.history_policy == HistoryPolicy.CONVERSATIONAL
