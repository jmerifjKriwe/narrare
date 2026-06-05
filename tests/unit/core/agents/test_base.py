"""Tests for NarrareAgent base class."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic_ai.models.test import TestModel

from narrare_core.agents import NarrareAgent
from narrare_core.agents.capabilities import NarrareMeta, NarrareUniversalRules

if TYPE_CHECKING:
    import pytest


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

        # NarrareObservability + NarrareUniversalRules + NarrareMeta
        # + TestCapability are always injected. get_instructions is
        # called once at init and once at run time for each capability.
        # call_log only tracks TestCapability → 2 calls.
        assert call_log == ["get_instructions called", "get_instructions called"]

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

    def test_all_production_agent_classes_inherit_adr026_capabilities(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Every exported production agent path receives ADR-026 capabilities.

        This patches the stable construction hook used by ``NarrareAgent`` instead
        of inspecting pydantic-ai private internals. If an agent stops calling the
        base constructor, no captured construction call is produced and this test
        fails for that concrete agent class.
        """
        import narrare_core.agents as agents_module
        import narrare_core.agents.base as base_module

        class CapturingPydanticAgent:
            calls: ClassVar[list[dict[str, Any]]] = []

            def __init__(self, **kwargs: Any) -> None:
                self.calls.append(kwargs)

            def output_validator(self, validator: Any) -> Any:
                return validator

            def tool(self, tool_func: Any) -> Any:
                return tool_func

        monkeypatch.setattr(base_module, "Agent", CapturingPydanticAgent)

        agent_classes = [
            exported
            for name in agents_module.__all__
            if inspect.isclass(exported := getattr(agents_module, name))
            and issubclass(exported, NarrareAgent)
            and exported is not NarrareAgent
        ]

        assert agent_classes, "No production NarrareAgent classes were discovered"

        for agent_class in agent_classes:
            before = len(CapturingPydanticAgent.calls)
            constructor: Any = agent_class
            constructor(model=object())
            assert len(CapturingPydanticAgent.calls) == before + 1, agent_class.__name__

            capabilities = CapturingPydanticAgent.calls[-1]["capabilities"]
            capability_types = {type(capability) for capability in capabilities}
            assert NarrareMeta in capability_types, agent_class.__name__
            assert NarrareUniversalRules in capability_types, agent_class.__name__
