"""Streaming tests for ConsistencyOrchestrator staged SSE events."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from narrare.consistency.schemas import ConsistencyResponse
from narrare.consistency.stage_schemas import ConsistencyStageEvent
from tests.unit.api.consistency.test_consistency_orchestrator import (
    _make_deps,
    _make_envelope,
    _make_orchestrator,
)


class TestStreamStagedCheck:
    """Verify staged stream event sequence and final response."""

    @pytest.mark.asyncio
    async def test_stream_yields_stage_events(self) -> None:
        """Streaming yields stage events and final response."""
        orchestrator, fact_agent, consistency_agent = _make_orchestrator()
        novel_id = uuid4()

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
            events: list[ConsistencyStageEvent | ConsistencyResponse] = []
            async for event in orchestrator.stream_staged_check(
                novel_id=novel_id,
                deps=_make_deps(),
                kb_summaries=[],
                timeline_envelopes=[_make_envelope()],
                language="en",
                max_chapter_tokens=2000,
            ):
                events.append(event)

        stage_events = [e for e in events if isinstance(e, ConsistencyStageEvent)]
        responses = [e for e in events if isinstance(e, ConsistencyResponse)]

        assert [e.status for e in stage_events[:3]] == ["start", "complete", "start"]
        assert any(e.status == "issue" for e in stage_events)
        assert stage_events[-1].stage == "complete"
        assert len(responses) == 1

    @pytest.mark.asyncio
    async def test_stream_complete_event_has_issue_count(self) -> None:
        """Final complete event includes issue count."""
        orchestrator, fact_agent, consistency_agent = _make_orchestrator()

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
            events: list[ConsistencyStageEvent | ConsistencyResponse] = []
            async for event in orchestrator.stream_staged_check(
                novel_id=uuid4(),
                deps=_make_deps(),
                kb_summaries=[],
                timeline_envelopes=[],
                language="en",
                max_chapter_tokens=2000,
            ):
                events.append(event)

        complete_events = [
            event
            for event in events
            if isinstance(event, ConsistencyStageEvent) and event.stage == "complete"
        ]
        assert len(complete_events) == 1
        assert complete_events[0].issues_found is not None
