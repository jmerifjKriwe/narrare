"""Tests for CharacterAgeCheck — character age consistency (PLAN-004 Phase 3).

Covers:
1. Characters with birth dates — no issues
2. Characters without birth dates — INFO issue
3. Multiple characters missing birth dates
4. Characters with None birth date — not flagged
5. Edge cases — empty events, no character_refs
6. Integration with run_deterministic_checks
"""

from __future__ import annotations

from typing import Any, cast

from narrare_core.analysis.age_check import CharacterAgeCheck
from narrare_core.analysis.temporal import run_deterministic_checks
from narrare_core.analysis.temporal_types import TemporalIssueSeverity


class TestCharacterAgeCheck:
    """CharacterAgeCheck detects characters without birth dates."""

    def test_all_characters_have_birth_dates_no_issues(self) -> None:
        """No issues when all referenced characters have birth dates."""
        events = [
            {
                "id": "1",
                "event_name": "Arrival",
                "character_refs": [{"name": "Frodo"}, {"name": "Aragorn"}],
            },
        ]
        character_ages = {"Frodo": "50", "Aragorn": "87"}
        issues = CharacterAgeCheck.check(cast("Any", events), cast("Any", character_ages))
        assert len(issues) == 0

    def test_character_without_birth_date_info_issue(self) -> None:
        """Characters referenced in events but not in ages dict produce INFO."""
        events = [
            {
                "id": "1",
                "event_name": "Arrival",
                "character_refs": [{"name": "Frodo"}, {"name": "Gandalf"}],
            },
        ]
        character_ages = {"Frodo": "50"}  # Gandalf missing
        issues = CharacterAgeCheck.check(cast("Any", events), cast("Any", character_ages))
        assert len(issues) == 1
        assert issues[0].severity == TemporalIssueSeverity.INFO
        assert issues[0].rule_id == "character_missing_birth_date"
        assert "Gandalf" in issues[0].description

    def test_multiple_characters_without_birth_date(self) -> None:
        """Multiple characters without birth dates reported in one issue."""
        events = [
            {
                "id": "1",
                "character_refs": [{"name": "Frodo"}, {"name": "Gandalf"}],
            },
            {
                "id": "2",
                "character_refs": [{"name": "Aragorn"}],
            },
        ]
        character_ages = {"Frodo": "50"}
        issues = CharacterAgeCheck.check(cast("Any", events), cast("Any", character_ages))
        assert len(issues) == 1
        assert "Gandalf" in issues[0].description
        assert "Aragorn" in issues[0].description

    def test_character_with_none_birth_date_not_flagged(self) -> None:
        """Characters in ages dict with None value are not flagged."""
        events = [
            {"id": "1", "character_refs": [{"name": "Frodo"}]},
        ]
        character_ages: dict[str, str | None] = {"Frodo": None}
        issues = CharacterAgeCheck.check(cast("Any", events), cast("Any", character_ages))
        assert len(issues) == 0

    def test_empty_events_no_issues(self) -> None:
        """Empty events list produces no issues."""
        issues = CharacterAgeCheck.check([], {"Frodo": "50"})
        assert len(issues) == 0

    def test_events_without_character_refs_no_issues(self) -> None:
        """Events without character_refs produce no issues."""
        events = [
            {"id": "1", "event_name": "World Event"},
        ]
        character_ages = {"Frodo": "50"}
        issues = CharacterAgeCheck.check(cast("Any", events), cast("Any", character_ages))
        assert len(issues) == 0

    def test_empty_character_refs_list_no_issues(self) -> None:
        """Events with empty character_refs list produce no issues."""
        events = [
            {"id": "1", "character_refs": []},
        ]
        character_ages: dict[str, str | None] = {}
        issues = CharacterAgeCheck.check(cast("Any", events), cast("Any", character_ages))
        assert len(issues) == 0


class TestCharacterAgeInDeterministicChecks:
    """CharacterAgeCheck integrates with run_deterministic_checks."""

    def test_character_age_issues_included(self) -> None:
        """CharacterAgeCheck issues are included when character_ages provided."""
        events = [
            {
                "id": "1",
                "event_name": "Arrival",
                "temporal_order": 1,
                "timestamp_raw": "Day 1",
                "chapter_reference": "Ch 1",
                "character_refs": [{"name": "Frodo"}, {"name": "Gandalf"}],
            },
        ]
        result = run_deterministic_checks(
            cast("Any", events),
            character_ages={"Frodo": "50"},  # Gandalf missing
        )
        age_issues = [i for i in result.issues if i.rule_id == "character_missing_birth_date"]
        assert len(age_issues) == 1
        assert "Gandalf" in age_issues[0].description

    def test_no_character_age_issues_when_not_provided(self) -> None:
        """No character age issues when character_ages is None."""
        events = [
            {
                "id": "1",
                "event_name": "Arrival",
                "temporal_order": 1,
                "timestamp_raw": "Day 1",
                "chapter_reference": "Ch 1",
                "character_refs": [{"name": "Frodo"}],
            },
        ]
        result = run_deterministic_checks(cast("Any", events))  # character_ages=None
        age_issues = [i for i in result.issues if i.rule_id == "character_missing_birth_date"]
        assert len(age_issues) == 0
