"""Tests for ConsistencyDeps timeline_events field — FIND-009.

Verifies that ConsistencyDeps accepts timeline_events and that
backward compatibility is maintained (empty list default).
"""

from __future__ import annotations

from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
)


class TestConsistencyDepsTimelineEvents:
    """timeline_events field on ConsistencyDeps."""

    def test_default_is_empty_list(self) -> None:
        """Without timeline_events, deps defaults to empty list."""
        deps = ConsistencyDeps()
        assert deps.timeline_events == []

    def test_accepts_timeline_events(self) -> None:
        """timeline_events accepts list of dicts with event data."""
        events = [
            {
                "event_name": "Aria arrives at Thornwall",
                "timestamp": "Ch 1",
                "character": "Aria",
                "location": "Thornwall Castle",
            },
            {
                "event_name": "Battle of the Gates",
                "timestamp": "Ch 3",
                "character": "Aria, Marcus",
                "location": "Thornwall Gates",
            },
        ]
        deps = ConsistencyDeps(timeline_events=events)
        assert len(deps.timeline_events) == 2
        assert deps.timeline_events[0]["event_name"] == "Aria arrives at Thornwall"
        assert deps.timeline_events[1]["character"] == "Aria, Marcus"

    def test_none_treated_as_empty_list(self) -> None:
        """Passing None for timeline_events results in empty list."""
        deps = ConsistencyDeps(timeline_events=None)
        assert deps.timeline_events == []

    def test_backward_compat_with_existing_fields(self) -> None:
        """Adding timeline_events doesn't break other fields."""
        deps = ConsistencyDeps(
            language="de",
            novel_id="novel-123",
            chapter_texts={"ch1": "Kapitel eins."},
            kb_entity_summaries=[{"entity_type": "character", "name": "Anna", "traits": ["brave"]}],
            timeline_events=[
                {
                    "event_name": "Anna arrives",
                    "timestamp": "Ch 1",
                    "character": "Anna",
                    "location": "Castle",
                },
            ],
            check_types=[ConsistencyCheckType.CHARACTER, ConsistencyCheckType.TIMELINE],
            existing_issue_count=2,
        )
        assert deps.language == "de"
        assert deps.novel_id == "novel-123"
        assert "ch1" in deps.chapter_texts
        assert len(deps.kb_entity_summaries) == 1
        assert len(deps.timeline_events) == 1
        assert ConsistencyCheckType.TIMELINE in deps.check_types
        assert deps.existing_issue_count == 2

    def test_events_with_partial_data(self) -> None:
        """Timeline events can have missing optional fields."""
        events = [
            {
                "event_name": "Mysterious event",
                "timestamp": "Ch 5",
                "character": "",
                "location": "",
            },
            {"event_name": "Another event", "timestamp": ""},
        ]
        deps = ConsistencyDeps(timeline_events=events)
        assert len(deps.timeline_events) == 2
        assert deps.timeline_events[0]["character"] == ""
        assert deps.timeline_events[1]["timestamp"] == ""
