"""Tests for WikiService — orchestration, graceful degradation, event publishing.

Test-Strategie:
- FakeWikiAgent für deterministische Agent-Tests
- FakeEventBus für Event-Publishing Tests
- Graceful degradation wird durch Fehler-Szenarien getestet
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from narrare_core.events.types import DomainEvent, EventType
from narrare_core.wiki.service import WikiService
from narrare_core.wiki.types import WikiEntityOutput, WikiGenerationDeps

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeWikiAgent:
    """Fake implementation of WikiAgentProtocol for deterministic tests."""

    def __init__(
        self,
        *,
        fail_on_generate: bool = False,
    ) -> None:
        self._fail_on_generate = fail_on_generate
        self.last_deps: WikiGenerationDeps | None = None

    async def generate_entity(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiEntityOutput:
        """Fake entity generation — returns predictable output or fails."""
        self.last_deps = deps
        if self._fail_on_generate:
            msg = "Simulated agent failure"
            raise RuntimeError(msg)
        return WikiEntityOutput(
            narrative_summary=f"A wiki summary for {deps.entity_name}.",
            role_in_story="A pivotal role in the narrative.",
            key_attributes=["trait_1", "trait_2", "trait_3"],
            relationships=[],
            character_arc="arc" if deps.entity_type == "character" else None,
        )

    async def generate_chapter(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> Any:
        """Fake chapter generation."""
        self.last_deps = deps
        return {
            "narrative_summary": f"Chapter summary for {deps.entity_name}.",
            "key_events": ["Event 1", "Event 2"],
            "entities_involved": [],
            "themes": [],
        }


@dataclass
class FakeEventBus:
    """Fake event bus that captures published events for test assertions."""

    published_events: list[DomainEvent] = field(default_factory=list)

    async def publish(self, event: DomainEvent) -> None:
        """Capture published event."""
        self.published_events.append(event)

    async def subscribe(self, event_type: str, handler: object) -> None:
        """No-op subscribe."""
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent() -> FakeWikiAgent:
    return FakeWikiAgent()


@pytest.fixture()
def failing_agent() -> FakeWikiAgent:
    return FakeWikiAgent(fail_on_generate=True)


@pytest.fixture()
def event_bus() -> FakeEventBus:
    return FakeEventBus()


@pytest.fixture()
def service(agent: FakeWikiAgent) -> WikiService:
    return WikiService(agent=agent)


@pytest.fixture()
def service_with_bus(agent: FakeWikiAgent, event_bus: FakeEventBus) -> WikiService:
    return WikiService(agent=agent, event_bus=event_bus)


@pytest.fixture()
def service_failing(failing_agent: FakeWikiAgent) -> WikiService:
    return WikiService(agent=failing_agent)


@pytest.fixture()
def deps() -> WikiGenerationDeps:
    return WikiGenerationDeps(
        language="en",
        genre="Fantasy",
        entity_type="character",
        entity_name="Eldrin",
        entity_body="Eldrin is a wizard.",
    )


# ---------------------------------------------------------------------------
# A. generate_entity_summary
# ---------------------------------------------------------------------------


class TestGenerateEntitySummary:
    """generate_entity_summary — happy path, graceful degradation."""

    @pytest.mark.asyncio
    async def test_generate_entity_summary_success(
        self, service: WikiService, deps: WikiGenerationDeps
    ) -> None:
        """Happy path: returns WikiEntityOutput."""
        result = await service.generate_entity_summary(
            entity_id="entity-1", novel_id="novel-1", deps=deps
        )
        assert result is not None
        assert isinstance(result, WikiEntityOutput)
        assert result.narrative_summary == "A wiki summary for Eldrin."
        assert result.role_in_story == "A pivotal role in the narrative."
        assert len(result.key_attributes) == 3

    @pytest.mark.asyncio
    async def test_generate_entity_summary_failure(
        self, service_failing: WikiService, deps: WikiGenerationDeps
    ) -> None:
        """Graceful degradation: returns None on agent failure."""
        result = await service_failing.generate_entity_summary(
            entity_id="entity-1", novel_id="novel-1", deps=deps
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_entity_summary_no_deps(self, service: WikiService) -> None:
        """Returns None when deps are not provided."""
        result = await service.generate_entity_summary(
            entity_id="entity-1", novel_id="novel-1", deps=None
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_entity_summary_passes_deps(
        self, agent: FakeWikiAgent, service: WikiService, deps: WikiGenerationDeps
    ) -> None:
        """Deps are correctly passed to the agent."""
        await service.generate_entity_summary(entity_id="entity-1", novel_id="novel-1", deps=deps)
        assert agent.last_deps is not None
        assert agent.last_deps.entity_name == "Eldrin"
        assert agent.last_deps.entity_type == "character"

    @pytest.mark.asyncio
    async def test_generate_entity_summary_with_location(self, service: WikiService) -> None:
        """Location entities work correctly."""
        location_deps = WikiGenerationDeps(
            language="en",
            genre="Fantasy",
            entity_type="location",
            entity_name="Forest",
            entity_body="A dark forest.",
        )
        result = await service.generate_entity_summary(
            entity_id="entity-2", novel_id="novel-1", deps=location_deps
        )
        assert result is not None
        assert result.character_arc is None  # locations don't have arcs


# ---------------------------------------------------------------------------
# B. get_summaries
# ---------------------------------------------------------------------------


class TestGetSummaries:
    """get_summaries — interface test (stub in Phase 1)."""

    @pytest.mark.asyncio
    async def test_get_summaries_returns_dict(self, service: WikiService) -> None:
        """Returns empty dict (Phase 1 stub)."""
        result = await service.get_summaries(
            entity_ids=["entity-1", "entity-2"], novel_id="novel-1"
        )
        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_summaries_empty_ids(self, service: WikiService) -> None:
        """Empty entity_ids returns empty dict."""
        result = await service.get_summaries(entity_ids=[], novel_id="novel-1")
        assert isinstance(result, dict)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# C. refresh_summary
# ---------------------------------------------------------------------------


class TestRefreshSummary:
    """refresh_summary — Phase 1 stub behavior."""

    @pytest.mark.asyncio
    async def test_refresh_summary_returns_none(self, service: WikiService) -> None:
        """Returns None in Phase 1 (deps must be external)."""
        result = await service.refresh_summary(entity_id="entity-1", novel_id="novel-1")
        assert result is None


# ---------------------------------------------------------------------------
# D. mark_all_stale
# ---------------------------------------------------------------------------


class TestMarkAllStale:
    """mark_all_stale — event publishing."""

    @pytest.mark.asyncio
    async def test_mark_all_stale_publishes_event(
        self, service_with_bus: WikiService, event_bus: FakeEventBus
    ) -> None:
        """Publishes WIKI_PROMPT_CHANGED event."""
        count = await service_with_bus.mark_all_stale(novel_id="novel-1", prompt_version="2.0.0")
        assert count == 0  # Phase 1: count handled by API layer
        assert len(event_bus.published_events) == 1
        event = event_bus.published_events[0]
        assert event.event_type == EventType.WIKI_PROMPT_CHANGED
        assert event.payload["novel_id"] == "novel-1"
        assert event.payload["prompt_version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_mark_all_stale_without_prompt_version(
        self, service_with_bus: WikiService, event_bus: FakeEventBus
    ) -> None:
        """Works without prompt_version."""
        count = await service_with_bus.mark_all_stale(novel_id="novel-1")
        assert count == 0
        assert len(event_bus.published_events) == 1
        assert event_bus.published_events[0].payload["prompt_version"] == ""

    @pytest.mark.asyncio
    async def test_mark_all_stale_without_event_bus(self, service: WikiService) -> None:
        """Works without event_bus (NullEventBus default)."""
        count = await service.mark_all_stale(novel_id="novel-1", prompt_version="2.0.0")
        assert count == 0  # No error with NullEventBus

    @pytest.mark.asyncio
    async def test_mark_all_stale_event_has_aggregate_id(
        self, service_with_bus: WikiService, event_bus: FakeEventBus
    ) -> None:
        """Event has a valid aggregate_id."""
        await service_with_bus.mark_all_stale(novel_id="novel-1")
        assert event_bus.published_events[0].aggregate_id is not None
