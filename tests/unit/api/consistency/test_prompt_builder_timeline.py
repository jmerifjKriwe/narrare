"""Tests for timeline event formatting in prompt_builder — FIND-009.

Verifies that _format_timeline_events produces correct output and that
empty timeline_events maintains backward compatibility (empty string).
"""

from __future__ import annotations

from narrare.consistency.prompt_builder import (
    build_consistency_prompt_variables,
)
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
)


def _deps(
    chapter_texts: dict[str, str] | None = None,
    kb_summaries: list[dict[str, object]] | None = None,
    timeline_events: list[dict[str, str]] | None = None,
) -> ConsistencyDeps:
    """Create ConsistencyDeps with sensible defaults for tests."""
    return ConsistencyDeps(
        chapter_texts=chapter_texts or {},
        kb_entity_summaries=kb_summaries or [],
        timeline_events=timeline_events or [],
    )


# --- A. Backward compatibility ---


class TestTimelineBackwardCompat:
    """Empty timeline_events produces empty timeline_position."""

    def test_empty_events_produces_empty_timeline_position(self) -> None:
        """When no timeline events, timeline_position is empty string."""
        deps = _deps()
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])
        assert result["timeline_position"] == ""

    def test_none_events_produces_empty_timeline_position(self) -> None:
        """When timeline_events is None, timeline_position is empty string."""
        deps = ConsistencyDeps(timeline_events=None)
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])
        assert result["timeline_position"] == ""

    def test_empty_timeline_does_not_affect_other_variables(self) -> None:
        """Empty timeline doesn't break chapter_texts or kb_entities."""
        deps = _deps(
            chapter_texts={"ch-1": "Hello"},
            kb_summaries=[{"entity_type": "character", "name": "Alice", "fields": {}}],
        )
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.CHARACTER])
        assert result["timeline_position"] == ""
        assert "### Chapter ch-1" in result["chapter_texts"]
        assert "Alice" in result["kb_entities"]


# --- B. Timeline formatting ---


class TestTimelineFormatting:
    """Timeline events are formatted into readable prompt data."""

    def test_single_event_with_all_fields(self) -> None:
        """Single event with all fields produces formatted line."""
        deps = _deps(
            timeline_events=[
                {
                    "event_name": "Aria arrives at Thornwall",
                    "timestamp": "Ch 1",
                    "character": "Aria",
                    "location": "Thornwall Castle",
                },
            ],
        )
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.TIMELINE])
        timeline = result["timeline_position"]

        assert "## Timeline Events" in timeline
        assert '- [Ch 1] "Aria arrives at Thornwall" — Aria; Thornwall Castle' in timeline

    def test_multiple_events_ordered(self) -> None:
        """Multiple events appear in order."""
        deps = _deps(
            timeline_events=[
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
                {
                    "event_name": "Marcus coronation",
                    "timestamp": "Ch 5",
                    "character": "Marcus",
                    "location": "Throne Room",
                },
            ],
        )
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.TIMELINE])
        timeline = result["timeline_position"]

        assert timeline.index("Ch 1") < timeline.index("Ch 3")
        assert timeline.index("Ch 3") < timeline.index("Ch 5")
        assert "Aria, Marcus" in timeline
        assert "Marcus coronation" in timeline

    def test_event_without_timestamp_shows_question_mark(self) -> None:
        """Events with empty timestamp show [?] placeholder."""
        deps = _deps(
            timeline_events=[
                {
                    "event_name": "Unknown event",
                    "timestamp": "",
                    "character": "Aria",
                    "location": "Forest",
                },
            ],
        )
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.TIMELINE])
        timeline = result["timeline_position"]

        assert '- [?] "Unknown event" — Aria; Forest' in timeline

    def test_event_with_no_character_or_location(self) -> None:
        """Event with no character/location omits detail section."""
        deps = _deps(
            timeline_events=[
                {
                    "event_name": "The Great Flood",
                    "timestamp": "Ch 7",
                    "character": "",
                    "location": "",
                },
            ],
        )
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.TIMELINE])
        timeline = result["timeline_position"]

        assert '- [Ch 7] "The Great Flood"' in timeline
        # No trailing "—" when no detail
        assert "—" not in timeline

    def test_event_with_character_but_no_location(self) -> None:
        """Event with character but no location shows only character."""
        deps = _deps(
            timeline_events=[
                {
                    "event_name": "Aria makes a decision",
                    "timestamp": "Ch 4",
                    "character": "Aria",
                    "location": "",
                },
            ],
        )
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.TIMELINE])
        timeline = result["timeline_position"]

        assert '- [Ch 4] "Aria makes a decision" — Aria' in timeline

    def test_event_with_location_but_no_character(self) -> None:
        """Event with location but no character shows only location."""
        deps = _deps(
            timeline_events=[
                {
                    "event_name": "Earthquake strikes",
                    "timestamp": "Ch 2",
                    "character": "",
                    "location": "Thornwall",
                },
            ],
        )
        result = build_consistency_prompt_variables(deps, [ConsistencyCheckType.TIMELINE])
        timeline = result["timeline_position"]

        assert '- [Ch 2] "Earthquake strikes" — Thornwall' in timeline


# --- C. Integration with build_consistency_prompt_variables ---


class TestBuildVariablesWithTimeline:
    """Timeline events integrated into the full prompt variable builder."""

    def test_all_variables_present_with_timeline(self) -> None:
        """All expected variables are present when timeline is included."""
        deps = _deps(
            chapter_texts={"ch-1": "Hello"},
            kb_summaries=[{"entity_type": "character", "name": "Alice", "fields": {}}],
            timeline_events=[
                {
                    "event_name": "Alice enters",
                    "timestamp": "Ch 1",
                    "character": "Alice",
                    "location": "Castle",
                },
            ],
        )
        result = build_consistency_prompt_variables(
            deps,
            [ConsistencyCheckType.CHARACTER, ConsistencyCheckType.TIMELINE],
        )

        assert "chapter_texts" in result
        assert "kb_entities" in result
        assert "timeline_position" in result
        assert "check_types" in result
        assert "Alice enters" in result["timeline_position"]

    def test_check_types_still_formatted_correctly(self) -> None:
        """Check types formatting not affected by timeline addition."""
        deps = _deps(timeline_events=[])
        result = build_consistency_prompt_variables(
            deps,
            [ConsistencyCheckType.TIMELINE, ConsistencyCheckType.PLOT],
        )
        assert result["check_types"] == "timeline, plot"
