"""Unit tests for ConsistencyOrchestrator — staged pipeline orchestration.

Tests the two-stage flow with Fake agents. No real DB, no real LLM.
ADR-044 Slice 3 validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

import pytest

from narrare.consistency.consistency_orchestrator import ConsistencyOrchestrator
from narrare.consistency.schemas import ConsistencyResponse
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
    ConsistencyIssue,
    ConsistencyOutput,
    ConsistencySeverity,
)
from narrare_core.agents.fact_extractor_types import (
    ExtractedFact,
    FactExtractorOutput,
    TimelineEventEnvelope,
)

if TYPE_CHECKING:
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer


# ---------------------------------------------------------------------------
# Fake agents
# ---------------------------------------------------------------------------


class FakeFactExtractorAgent:
    """Fake fact extractor returning preconfigured output."""

    def __init__(self, output: FactExtractorOutput | None = None) -> None:
        self._output = output or FactExtractorOutput(
            facts=[
                ExtractedFact(
                    fact_type="character_state",
                    subject="Anna",
                    predicate="has eye color",
                    object_value="blue",
                    chapter_id="ch-1",
                    evidence_text="Anna's blue eyes sparkled.",
                    confidence=0.95,
                ),
            ],
            assessment_summary="Extracted 1 fact.",
        )
        self.calls: list[dict[str, object]] = []

    async def run(self, prompt: str, deps: object, **kwargs: object) -> FactExtractorOutput:
        self.calls.append({"prompt": prompt, "deps": deps})
        return self._output


class FakeConsistencyAgent:
    """Fake consistency agent returning preconfigured output."""

    def __init__(self, output: ConsistencyOutput | None = None) -> None:
        self._output = output or ConsistencyOutput(
            issues=[
                ConsistencyIssue(
                    check_type=ConsistencyCheckType.CHARACTER,
                    severity=ConsistencySeverity.WARNING,
                    description="Anna's eye color contradicts KB entry.",
                    locations=["Chapter 1", "KB: Anna"],
                    conflicting_facts=["blue eyes (chapter)", "green eyes (KB)"],
                    suggestion="Unify Anna's eye color across sources.",
                    confidence=0.9,
                ),
            ],
            overall_assessment="1 issue found.",
            checked_types=[ConsistencyCheckType.CHARACTER],
        )
        self.calls: list[dict[str, object]] = []

    async def run(self, prompt: str, deps: object, **kwargs: object) -> ConsistencyOutput:
        self.calls.append({"prompt": prompt, "deps": deps})
        return self._output


class FakeComposer:
    """Fake PromptComposer returning simple prompts."""

    async def build(self, intent: object, context: object) -> _FakeComposed:
        return _FakeComposed("System prompt.", "User prompt.")


class _FakeComposed:
    def __init__(self, system: str, user: str) -> None:
        self.system = system
        self.user = user


class FakeRegistry:
    """Fake ModelRegistry returning a placeholder model."""

    async def get_model(self, config: object) -> object:
        return object()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_envelope(event_name: str = "Battle of Thornwall") -> TimelineEventEnvelope:
    return TimelineEventEnvelope(
        event_id=str(uuid4()),
        event_name=event_name,
        timestamp_raw="Day 15, Morning",
        timestamp_normalized="day_15_morning",
        temporal_order=1,
        source_chapter_id="ch-1",
        character_refs=[{"id": "e-1", "name": "Anna", "status": "active"}],
        location_ref={"id": "l-1", "name": "Thornwall", "status": "active"},
        causes=["Troll invasion"],
        consequences=["Anna's scar"],
        source="narration",
        confidence=0.9,
        is_confirmed=True,
    )


def _make_deps() -> ConsistencyDeps:
    """Create a minimal ConsistencyDeps-like object."""
    ch_id = str(uuid4())
    return ConsistencyDeps(
        language="en",
        novel_id=str(uuid4()),
        chapter_texts={ch_id: "Anna walked through the forest."},
        kb_entity_summaries=[{"entity_type": "character", "name": "Anna", "fields": {}}],
        timeline_events=[
            {"event_name": "test", "timestamp": "Day 1", "character": "", "location": ""}
        ],
        check_types=[ConsistencyCheckType.CHARACTER],
    )


def _make_config() -> ResolvedModelConfig:
    from narrare_core.llm import ResolvedModelConfig

    return ResolvedModelConfig(
        provider_name="test",
        model_id="test",
        temperature=0.3,
        max_tokens=2048,
    )


def _make_orchestrator(
    fact_output: FactExtractorOutput | None = None,
    consistency_output: ConsistencyOutput | None = None,
) -> tuple[ConsistencyOrchestrator, FakeFactExtractorAgent, FakeConsistencyAgent]:
    """Create orchestrator with fake agents for testing."""
    registry = FakeRegistry()
    composer = FakeComposer()
    fact_agent = FakeFactExtractorAgent(output=fact_output)
    consistency_agent = FakeConsistencyAgent(output=consistency_output)

    orchestrator = ConsistencyOrchestrator(
        # Cast is safe here: FakeRegistry implements the get_model method used.
        registry=cast("ModelRegistry", registry),
        fact_extractor_config=_make_config(),
        consistency_config=_make_config(),
        # Cast is safe here: FakeComposer implements the build method used.
        composer=cast("PromptComposer", composer),
    )
    return orchestrator, fact_agent, consistency_agent


# ---------------------------------------------------------------------------
# Tests — run_staged_check
# ---------------------------------------------------------------------------


class TestRunStagedCheck:
    @pytest.mark.asyncio
    async def test_staged_check_returns_response(self) -> None:
        """Staged pipeline returns a ConsistencyResponse."""
        orchestrator, fact_agent, consistency_agent = _make_orchestrator()
        novel_id = uuid4()
        deps = _make_deps()
        envelopes = [_make_envelope()]
        kb_summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Anna", "fields": {}},
        ]

        from unittest.mock import patch

        with (
            patch(
                "narrare_core.agents.fact_extractor_agent.FactExtractorAgent",
                return_value=fact_agent,
            ),
            patch(
                "narrare_core.agents.consistency_agent.ConsistencyAgent",
                return_value=consistency_agent,
            ),
        ):
            result = await orchestrator.run_staged_check(
                novel_id=novel_id,
                deps=deps,
                kb_summaries=kb_summaries,
                timeline_envelopes=envelopes,
                language="en",
                max_chapter_tokens=2000,
            )

        assert isinstance(result, ConsistencyResponse)
        assert result.novel_id == novel_id
        assert result.total_issues >= 0

    @pytest.mark.asyncio
    async def test_staged_check_calls_fact_extractor(self) -> None:
        """Stage 1 (FactExtractor) is called during staged pipeline."""
        fact_output = FactExtractorOutput(facts=[], assessment_summary="No facts.")
        orchestrator, fact_agent, consistency_agent = _make_orchestrator(
            fact_output=fact_output,
        )
        novel_id = uuid4()
        deps = _make_deps()
        envelopes = [_make_envelope()]

        from unittest.mock import patch

        with (
            patch(
                "narrare_core.agents.fact_extractor_agent.FactExtractorAgent",
                return_value=fact_agent,
            ),
            patch(
                "narrare_core.agents.consistency_agent.ConsistencyAgent",
                return_value=consistency_agent,
            ),
        ):
            await orchestrator.run_staged_check(
                novel_id=novel_id,
                deps=deps,
                kb_summaries=[],
                timeline_envelopes=envelopes,
                language="en",
                max_chapter_tokens=2000,
            )

        assert len(fact_agent.calls) == 1

    @pytest.mark.asyncio
    async def test_staged_check_enriches_deps_with_facts(self) -> None:
        """Stage 2 receives enriched ConsistencyDeps with extracted_facts."""
        fact_output = FactExtractorOutput(
            facts=[
                ExtractedFact(
                    fact_type="character_state",
                    subject="Anna",
                    predicate="has eye color",
                    object_value="blue",
                    chapter_id="ch-1",
                    evidence_text="Anna's blue eyes.",
                    confidence=0.9,
                ),
            ],
            assessment_summary="1 fact.",
        )
        orchestrator, fact_agent, consistency_agent = _make_orchestrator(
            fact_output=fact_output,
        )
        novel_id = uuid4()
        deps = _make_deps()

        from unittest.mock import patch

        with (
            patch(
                "narrare_core.agents.fact_extractor_agent.FactExtractorAgent",
                return_value=fact_agent,
            ),
            patch(
                "narrare_core.agents.consistency_agent.ConsistencyAgent",
                return_value=consistency_agent,
            ),
        ):
            await orchestrator.run_staged_check(
                novel_id=novel_id,
                deps=deps,
                kb_summaries=[],
                timeline_envelopes=[],
                language="en",
                max_chapter_tokens=2000,
            )

        # Consistency agent should have been called
        assert len(consistency_agent.calls) == 1
        # The deps passed to consistency agent should have extracted_facts
        consistency_deps = cast("ConsistencyDeps", consistency_agent.calls[0]["deps"])
        assert consistency_deps.has_structured_input is True
        assert consistency_deps.extracted_facts is not None
        assert len(consistency_deps.extracted_facts) == 1
