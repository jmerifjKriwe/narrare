"""Tests for DurationImpossibilityCheck — impossible durations / event sequences.

Covers:
1. Empty events, clean timeline
2. Same-character/location conflict (WARNING)
3. Same-character/same-location (no issue)
4. Different characters/different location (no issue)
5. Death before birth (ERROR)
6. Death after birth (no issue)
7. Death without birth (no issue)
8. Impossibly fast travel (INFO)
9. Consecutive same-location (no issue)
10. Non-consecutive different-location (no issue)
11. Missing fields handled gracefully
12. Multiple events same order triggering multiple conflicts
13. Events without order skipped

Extracted from ``test_temporal.py`` to resolve RULE-04 (file-size limit).
"""

from __future__ import annotations

from narrare_core.analysis.duration_check import DurationImpossibilityCheck
from narrare_core.analysis.temporal_types import TemporalIssueSeverity


def _MAKE_EVENT(eid: str, **kw: object) -> dict[str, object]:
    """Create an event dict for testing."""
    return {"id": eid, "event_name": f"Ev {eid}", **kw}


class TestDurationImpossibilityCheck:
    """DurationImpossibilityCheck detects impossible event sequences."""

    def test_empty_events_returns_empty(self) -> None:
        """Empty events list returns no issues."""
        issues = DurationImpossibilityCheck.check([])
        assert issues == []

    def test_no_issues_with_clean_timeline(self) -> None:
        """Events with unique orders and no location conflicts produce no issues."""
        events = [
            _MAKE_EVENT("1", temporal_order=1),
            _MAKE_EVENT("2", temporal_order=2),
            _MAKE_EVENT("3", temporal_order=3),
        ]
        issues = DurationImpossibilityCheck.check(events)
        assert issues == []

    def test_same_character_different_locations_warning(self) -> None:
        """Same char at same order in different locations → WARNING."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=1,
                location_ref={"id": "loc-2", "name": "Tavern"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "same_character_different_location"]
        assert len(relevant) == 1
        assert relevant[0].severity == TemporalIssueSeverity.WARNING
        assert "John" in relevant[0].description
        assert "Castle" in relevant[0].description
        assert "Tavern" in relevant[0].description

    def test_same_character_same_location_no_issue(self) -> None:
        """Same char at same order in the same location → no issue."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=1,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "same_character_different_location"]
        assert len(relevant) == 0

    def test_different_characters_no_conflict(self) -> None:
        """Different chars at same order in different locations → no issue."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=1,
                location_ref={"id": "loc-2", "name": "Tavern"},
                character_refs=[{"id": "ch-2", "name": "Mary"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "same_character_different_location"]
        assert len(relevant) == 0

    def test_death_before_birth_error(self) -> None:
        """Death event before birth event for same char → ERROR."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                event_type="death",
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=5,
                event_type="birth",
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "death_before_birth"]
        assert len(relevant) == 1
        assert relevant[0].severity == TemporalIssueSeverity.ERROR
        assert "John" in relevant[0].description

    def test_death_after_birth_no_issue(self) -> None:
        """Death after birth is fine → no issue."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                event_type="birth",
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=5,
                event_type="death",
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "death_before_birth"]
        assert len(relevant) == 0

    def test_death_without_birth_no_issue(self) -> None:
        """Death event without any birth event → no issue."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=3,
                event_type="death",
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "death_before_birth"]
        assert len(relevant) == 0

    def test_impossibly_fast_travel_info(self) -> None:
        """Consecutive orders with different locations → INFO."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=2,
                location_ref={"id": "loc-2", "name": "Tavern"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "impossibly_fast_travel"]
        assert len(relevant) == 1
        assert relevant[0].severity == TemporalIssueSeverity.INFO
        assert "Castle" in relevant[0].description
        assert "Tavern" in relevant[0].description

    def test_consecutive_same_location_no_travel_issue(self) -> None:
        """Consecutive orders with same location → no travel issue."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=2,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "impossibly_fast_travel"]
        assert len(relevant) == 0

    def test_non_consecutive_order_different_location_no_issue(self) -> None:
        """Non-consecutive orders with different locations → no travel issue."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=5,
                location_ref={"id": "loc-2", "name": "Tavern"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "impossibly_fast_travel"]
        assert len(relevant) == 0

    def test_missing_fields_handled_gracefully(self) -> None:
        """Missing optional fields (location_ref, event_type) do not crash."""
        events = [
            _MAKE_EVENT("1", temporal_order=1),
            _MAKE_EVENT("2", temporal_order=2),
        ]
        # No location_ref, no event_type, no character_refs — should not crash
        issues = DurationImpossibilityCheck.check(events)
        assert isinstance(issues, list)

    def test_char_from_multiple_events_triggers_once_per_pair(self) -> None:
        """Multiple events at the same order with same char trigger each conflict."""
        events = [
            _MAKE_EVENT(
                "1",
                temporal_order=1,
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                temporal_order=1,
                location_ref={"id": "loc-2", "name": "Tavern"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "3",
                temporal_order=1,
                location_ref={"id": "loc-3", "name": "Forest"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        relevant = [i for i in issues if i.rule_id == "same_character_different_location"]
        # John at Castle is the first occurrence; then conflicts with Tavern and Forest
        assert len(relevant) == 2

    def test_events_without_order_are_skipped(self) -> None:
        """Events without temporal_order are not checked for location conflicts."""
        events = [
            _MAKE_EVENT(
                "1",
                location_ref={"id": "loc-1", "name": "Castle"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
            _MAKE_EVENT(
                "2",
                location_ref={"id": "loc-2", "name": "Tavern"},
                character_refs=[{"id": "ch-1", "name": "John"}],
            ),
        ]
        issues = DurationImpossibilityCheck.check(events)
        # No issues because both events have no temporal_order → filtered out
        assert len(issues) == 0
