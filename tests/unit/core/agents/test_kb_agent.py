"""Tests für KBAgent — Instantiation, Tools, Tool-Verhalten.

Test-Strategie:
- TestModel für deterministische Tests
- RunContext wie in test_draft_agent.py konstruiert
- Keine echten LLM-Calls (RULE-01)
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset

from narrare_core.agents.kb_agent import KBAgent, KBDeps


@pytest.fixture()
def test_model() -> TestModel:
    return TestModel()


@pytest.fixture()
def kb_agent(test_model: TestModel) -> KBAgent:
    return KBAgent(model=test_model)


@pytest.fixture()
def kb_deps() -> KBDeps:
    return KBDeps()


@pytest.fixture()
def kb_run_context(test_model: TestModel, kb_deps: KBDeps) -> RunContext[KBDeps]:
    return RunContext[KBDeps](deps=kb_deps, model=test_model, usage=RunUsage())


def _ctx(test_model: TestModel, deps: KBDeps) -> RunContext[KBDeps]:
    return RunContext[KBDeps](deps=deps, model=test_model, usage=RunUsage())


class TestInstantiation:
    """A. Instantiation & Basic (3 Tests)."""

    def test_kb_agent_can_be_instantiated(self, kb_agent: KBAgent) -> None:
        assert isinstance(kb_agent, KBAgent)
        assert kb_agent._agent is not None

    def test_kbdeps_defaults(self) -> None:
        deps = KBDeps()
        assert deps.kb_service is None

    def test_output_type_is_none(self, kb_agent: KBAgent) -> None:
        """output_type=None → Tool-Provider, kein ausführbarer Agent."""
        assert kb_agent._agent is not None


class TestTools:
    """B. Tools — Toolset, Tool-Verhalten, Fallback + Happy Path (11 Tests)."""

    def test_get_toolset_returns_function_toolset(self, kb_agent: KBAgent) -> None:
        toolset = kb_agent.get_toolset()
        assert isinstance(toolset, FunctionToolset)

    def test_toolset_has_three_tools(self, kb_agent: KBAgent) -> None:
        assert len(kb_agent.get_toolset().tools) == 3

    def test_tools_have_defer_loading(self, kb_agent: KBAgent) -> None:
        for name, tool in kb_agent.get_toolset().tools.items():
            assert tool.defer_loading is True, f"Tool {name} nicht defer_loading=True"

    @pytest.mark.asyncio
    async def test_search_kb_fallback_without_service(
        self, kb_agent: KBAgent, kb_run_context: RunContext[KBDeps]
    ) -> None:
        result = await kb_agent.search_kb(kb_run_context, query="test")
        assert result == "KB search is not available. No KB service configured."

    @pytest.mark.asyncio
    async def test_get_entity_fallback_without_service(
        self, kb_agent: KBAgent, kb_run_context: RunContext[KBDeps]
    ) -> None:
        result = await kb_agent.get_entity(kb_run_context, name="Anna")
        assert result == "Entity 'Anna' not found. KB service is not available."

    @pytest.mark.asyncio
    async def test_get_related_fallback_without_service(
        self, kb_agent: KBAgent, kb_run_context: RunContext[KBDeps]
    ) -> None:
        result = await kb_agent.get_related_entities(kb_run_context, entity_name="Anna")
        assert result == "No related entities found for 'Anna'."

    @pytest.mark.asyncio
    async def test_search_kb_service_error(self, kb_agent: KBAgent, test_model: TestModel) -> None:
        class BrokenService:
            async def search(self, query: str, **kwargs: object) -> None:
                raise ConnectionError("Connection refused")

        result = await kb_agent.search_kb(
            _ctx(test_model, KBDeps(kb_service=BrokenService())), query="test"
        )
        assert "KB search failed" in result and "Connection refused" in result

    @pytest.mark.asyncio
    async def test_get_entity_service_error(self, kb_agent: KBAgent, test_model: TestModel) -> None:
        class BrokenService:
            async def get_by_name(self, name: str) -> None:
                raise ValueError("Not found in DB")

        result = await kb_agent.get_entity(
            _ctx(test_model, KBDeps(kb_service=BrokenService())), name="Ghost"
        )
        assert "KB lookup failed" in result and "Not found in DB" in result

    @pytest.mark.asyncio
    async def test_search_kb_with_results(self, kb_agent: KBAgent, test_model: TestModel) -> None:
        class MockService:
            async def search(self, query: str, **kwargs: object) -> list[SimpleNamespace]:
                return [SimpleNamespace(name="Anna", entity_type="character", body="Hero.")]

        result = await kb_agent.search_kb(
            _ctx(test_model, KBDeps(kb_service=MockService())), query="Anna"
        )
        assert "Found KB entries" in result and "Anna" in result and "[character]" in result

    @pytest.mark.asyncio
    async def test_get_entity_with_results(self, kb_agent: KBAgent, test_model: TestModel) -> None:
        class MockService:
            async def get_by_name(self, name: str) -> SimpleNamespace:
                return SimpleNamespace(
                    name="Anna", entity_type="character", body="Hero.", tags=[], status="draft"
                )

        result = await kb_agent.get_entity(
            _ctx(test_model, KBDeps(kb_service=MockService())), name="Anna"
        )
        assert "Entity: Anna" in result and "Type: character" in result

    @pytest.mark.asyncio
    async def test_get_related_with_results(self, kb_agent: KBAgent, test_model: TestModel) -> None:
        class MockService:
            async def get_by_name(self, name: str) -> SimpleNamespace:
                return SimpleNamespace(id="e1", name="Anna", entity_type="character", body=".")

            async def get_related_entries(
                self, entity_id: str, rel_type: str | None = None
            ) -> list[SimpleNamespace]:
                return [SimpleNamespace(target_name="Peter", rel_type="ally")]

        result = await kb_agent.get_related_entities(
            _ctx(test_model, KBDeps(kb_service=MockService())), entity_name="Anna"
        )
        assert "Entities related to 'Anna'" in result and "Peter (ally)" in result

    @pytest.mark.asyncio
    async def test_get_related_service_error(
        self, kb_agent: KBAgent, test_model: TestModel
    ) -> None:
        class BrokenService:
            async def get_by_name(self, name: str) -> SimpleNamespace:
                return SimpleNamespace(id="e1", name="Anna", entity_type="character", body=".")

            async def get_related_entries(
                self, entity_id: str, rel_type: str | None = None
            ) -> None:
                raise RuntimeError("DB timeout")

        result = await kb_agent.get_related_entities(
            _ctx(test_model, KBDeps(kb_service=BrokenService())), entity_name="Anna"
        )
        assert "KB relationship lookup failed" in result and "DB timeout" in result
