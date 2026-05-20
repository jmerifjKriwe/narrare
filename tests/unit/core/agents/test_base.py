"""Tests for NarrareAgent base class."""

from __future__ import annotations

from pydantic_ai.models.test import TestModel

from narrare_core.agents import NarrareAgent


class TestNarrareAgent:
    """Test suite for NarrareAgent base class."""

    async def test_can_be_instantiated(self) -> None:
        """Basis-Klasse kann mit TestModel instanziiert werden."""
        model = TestModel()

        class MyAgent(NarrareAgent[None, str]):
            pass

        agent = MyAgent(model=model, deps_type=type(None), output_type=str)
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"

    async def test_can_be_instantiated_without_output_type(self) -> None:
        """Basis-Klasse kann ohne output_type instanziiert werden (default = str)."""
        model = TestModel()

        class MyAgent(NarrareAgent[None, str]):
            pass

        agent = MyAgent(model=model, deps_type=type(None))
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"

    async def test_with_custom_output_text(self) -> None:
        """TestModel mit custom_output_text gibt den Text zurück."""
        model = TestModel(custom_output_text="Custom response")

        class MyAgent(NarrareAgent[None, str]):
            pass

        agent = MyAgent(model=model, deps_type=type(None), output_type=str)
        result = await agent.run("test", deps=None)
        assert result == "Custom response"

    async def test_with_system_prompt(self) -> None:
        """system_prompt wird an pydantic-ai durchgereicht."""
        model = TestModel()

        class MyAgent(NarrareAgent[None, str]):
            pass

        agent = MyAgent(
            model=model,
            deps_type=type(None),
            output_type=str,
            system_prompt="Du bist ein hilfreicher Assistent.",
        )
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"

    async def test_abc_marker_does_not_prevent_instantiation(self) -> None:
        """ABC-Marker verhindert keine Instantiierung (noch keine @abstractmethod).

        NarrareAgent erbt von ABC als Dokumentation, hat aber in Phase 0.3
        keine abstrakten Methoden. Direkte Instantiierung ist daher erlaubt.
        """
        agent = NarrareAgent(
            model=TestModel(),
            deps_type=type(None),
            output_type=str,
        )
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"

    async def test_capabilities_are_passed_through(self) -> None:
        """Zusätzliche Capabilities werden an pydantic-ai durchgereicht."""
        from dataclasses import dataclass

        from pydantic_ai.capabilities import AbstractCapability

        call_log: list[str] = []

        @dataclass
        class TestCapability(AbstractCapability):
            def get_instructions(self) -> str | None:
                call_log.append("get_instructions called")
                return None

        model = TestModel()

        class MyAgent(NarrareAgent[None, str]):
            pass

        agent = MyAgent(
            model=model,
            deps_type=type(None),
            output_type=str,
            capabilities=[TestCapability()],
        )
        result = await agent.run("test", deps=None)
        assert result == "success (no tool calls)"
        # NarrareObservability is always injected + TestCapability
        assert call_log == ["get_instructions called"]

    async def test_with_non_none_deps(self) -> None:
        """Agent kann mit benutzerdefinierten Dependencies verwendet werden."""
        from dataclasses import dataclass

        @dataclass
        class MyDeps:
            user_name: str

        model = TestModel()

        class MyAgent(NarrareAgent[MyDeps, str]):
            pass

        agent = MyAgent(model=model, deps_type=MyDeps, output_type=str)

        # Agent with non-None deps type
        result = await agent.run("Hallo", deps=MyDeps(user_name="Alice"))
        assert result == "success (no tool calls)"
