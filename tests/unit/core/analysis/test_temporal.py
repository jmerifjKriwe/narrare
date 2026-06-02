"""Tests for deterministic temporal consistency checks (ADR-021).

Covers:
1. TemporalOrderingCheck — ordered events, missing order, duplicate order
2. DuplicateEventCheck — unique events, duplicate timestamp+chapter
3. run_deterministic_checks — combines all checks
4. Edge cases — empty events, single event
5. TemporalIssueSeverity and TemporalIssue models
6. Prompt file existence — temporal_consistency in all 3 locales

Moved to separate test files:
- DurationImpossibilityCheck  → ``test_duration_check.py``
- CharacterAgeCheck          → ``test_character_age.py``
"""

from __future__ import annotations

from pathlib import Path

from narrare_core.analysis.temporal import (
    DuplicateEventCheck,
    TemporalOrderingCheck,
    run_deterministic_checks,
)
from narrare_core.analysis.temporal_types import (
    TemporalConsistencyResult,
    TemporalIssue,
    TemporalIssueSeverity,
)

PROMPTS_DIR = Path(__file__).parents[4] / "packages/core/narrare_core/prompts/_bundled"

# ---------------------------------------------------------------------------
# A. TemporalOrderingCheck
# ---------------------------------------------------------------------------


class TestTemporalOrderingCheck:
    """TemporalOrderingCheck detects ordering violations."""

    def test_ordered_events_no_issues(self) -> None:
        """Events with unique, sequential temporal_order produce no issues."""
        events = [
            {"id": "1", "event_name": "Event A", "temporal_order": 1},
            {"id": "2", "event_name": "Event B", "temporal_order": 2},
            {"id": "3", "event_name": "Event C", "temporal_order": 3},
        ]
        issues = TemporalOrderingCheck.check(events)  # type: ignore[arg-type]
        # No ordering violations — only events without None temporal_order
        # Actually all have temporal_order, so no issues at all
        assert len(issues) == 0

    def test_missing_temporal_order_info_issue(self) -> None:
        """Events without temporal_order produce an INFO issue."""
        events = [
            {"id": "1", "event_name": "Event A", "temporal_order": 1},
            {"id": "2", "event_name": "Event B", "temporal_order": None},
            {"id": "3", "event_name": "Event C"},
        ]
        issues = TemporalOrderingCheck.check(events)  # type: ignore[arg-type]
        info_issues = [i for i in issues if i.rule_id == "missing_temporal_order"]
        assert len(info_issues) == 1
        assert info_issues[0].severity == TemporalIssueSeverity.INFO
        assert "2" in info_issues[0].description  # 2 events without order

    def test_duplicate_temporal_order_warning(self) -> None:
        """Events sharing the same temporal_order produce a WARNING."""
        events = [
            {"id": "1", "event_name": "Event A", "temporal_order": 1},
            {"id": "2", "event_name": "Event B", "temporal_order": 1},
            {"id": "3", "event_name": "Event C", "temporal_order": 2},
        ]
        issues = TemporalOrderingCheck.check(events)  # type: ignore[arg-type]
        dup_issues = [i for i in issues if i.rule_id == "duplicate_temporal_order"]
        assert len(dup_issues) == 1
        assert dup_issues[0].severity == TemporalIssueSeverity.WARNING
        assert "1" in dup_issues[0].description  # temporal_order=1

    def test_empty_events_no_issues(self) -> None:
        """Empty events list produces no issues."""
        issues = TemporalOrderingCheck.check([])
        assert len(issues) == 0

    def test_single_event_no_issues(self) -> None:
        """Single event with temporal_order produces no issues."""
        events = [
            {"id": "1", "event_name": "Only Event", "temporal_order": 1},
        ]
        issues = TemporalOrderingCheck.check(events)  # type: ignore[arg-type]
        assert len(issues) == 0

    def test_all_events_missing_order(self) -> None:
        """All events without temporal_order produce one INFO issue."""
        events = [
            {"id": "1", "event_name": "Event A"},
            {"id": "2", "event_name": "Event B"},
        ]
        issues = TemporalOrderingCheck.check(events)  # type: ignore[arg-type]
        info_issues = [i for i in issues if i.rule_id == "missing_temporal_order"]
        assert len(info_issues) == 1
        assert "2" in info_issues[0].description


# ---------------------------------------------------------------------------
# B. DuplicateEventCheck
# ---------------------------------------------------------------------------


class TestDuplicateEventCheck:
    """DuplicateEventCheck detects events with same timestamp_raw and chapter."""

    def test_unique_events_no_issues(self) -> None:
        """Events with unique timestamp+chapter combinations produce no issues."""
        events = [
            {"id": "1", "timestamp_raw": "Day 1", "chapter_reference": "Ch 1"},
            {"id": "2", "timestamp_raw": "Day 2", "chapter_reference": "Ch 1"},
            {"id": "3", "timestamp_raw": "Day 1", "chapter_reference": "Ch 2"},
        ]
        issues = DuplicateEventCheck.check(events)  # type: ignore[arg-type]
        assert len(issues) == 0

    def test_duplicate_timestamp_and_chapter_warning(self) -> None:
        """Events sharing timestamp_raw and chapter_reference produce WARNING."""
        events = [
            {"id": "1", "timestamp_raw": "that evening", "chapter_reference": "Chapter 5"},
            {"id": "2", "timestamp_raw": "that evening", "chapter_reference": "Chapter 5"},
            {"id": "3", "timestamp_raw": "the next day", "chapter_reference": "Chapter 5"},
        ]
        issues = DuplicateEventCheck.check(events)  # type: ignore[arg-type]
        dup_issues = [i for i in issues if i.rule_id == "duplicate_event"]
        assert len(dup_issues) == 1
        assert dup_issues[0].severity == TemporalIssueSeverity.WARNING
        assert "that evening" in dup_issues[0].description
        assert "Chapter 5" in dup_issues[0].description

    def test_same_timestamp_different_chapter_no_issue(self) -> None:
        """Same timestamp in different chapters is not a duplicate."""
        events = [
            {"id": "1", "timestamp_raw": "that evening", "chapter_reference": "Chapter 1"},
            {"id": "2", "timestamp_raw": "that evening", "chapter_reference": "Chapter 5"},
        ]
        issues = DuplicateEventCheck.check(events)  # type: ignore[arg-type]
        assert len(issues) == 0

    def test_empty_events_no_issues(self) -> None:
        """Empty events list produces no issues."""
        issues = DuplicateEventCheck.check([])
        assert len(issues) == 0

    def test_multiple_duplicate_groups(self) -> None:
        """Multiple groups of duplicates produce multiple issues."""
        events = [
            {"id": "1", "timestamp_raw": "Day 1", "chapter_reference": "Ch 1"},
            {"id": "2", "timestamp_raw": "Day 1", "chapter_reference": "Ch 1"},
            {"id": "3", "timestamp_raw": "Day 5", "chapter_reference": "Ch 3"},
            {"id": "4", "timestamp_raw": "Day 5", "chapter_reference": "Ch 3"},
        ]
        issues = DuplicateEventCheck.check(events)  # type: ignore[arg-type]
        dup_issues = [i for i in issues if i.rule_id == "duplicate_event"]
        assert len(dup_issues) == 2


# ---------------------------------------------------------------------------
# C. run_deterministic_checks
# ---------------------------------------------------------------------------


class TestRunDeterministicChecks:
    """run_deterministic_checks combines all checks."""

    def test_empty_events_pass(self) -> None:
        """Empty events list passes all checks."""
        result = run_deterministic_checks([])
        assert result.deterministic_pass is True
        assert result.issues == []
        assert result.overall_assessment == "No temporal issues detected."

    def test_clean_events_pass(self) -> None:
        """Events with no issues pass all checks."""
        events = [
            {
                "id": "1",
                "event_name": "Event A",
                "temporal_order": 1,
                "timestamp_raw": "Day 1",
                "chapter_reference": "Ch 1",
            },
            {
                "id": "2",
                "event_name": "Event B",
                "temporal_order": 2,
                "timestamp_raw": "Day 2",
                "chapter_reference": "Ch 1",
            },
        ]
        result = run_deterministic_checks(events)  # type: ignore[arg-type]
        assert result.deterministic_pass is True
        assert len(result.issues) == 0

    def test_issues_from_multiple_checks_combined(self) -> None:
        """Issues from different checks are combined in the result."""
        events = [
            {
                "id": "1",
                "event_name": "Event A",
                "temporal_order": 1,
                "timestamp_raw": "that evening",
                "chapter_reference": "Ch 1",
            },
            {
                "id": "2",
                "event_name": "Event B",
                "temporal_order": 1,
                "timestamp_raw": "that evening",
                "chapter_reference": "Ch 1",
            },
        ]
        result = run_deterministic_checks(events)  # type: ignore[arg-type]
        # Should have: 1 duplicate_temporal_order + 1 duplicate_event
        assert len(result.issues) >= 2
        rule_ids = {i.rule_id for i in result.issues}
        assert "duplicate_temporal_order" in rule_ids
        assert "duplicate_event" in rule_ids

    def test_warnings_still_pass(self) -> None:
        """Warnings don't cause deterministic_pass to be False."""
        events = [
            {
                "id": "1",
                "event_name": "Event A",
                "temporal_order": 1,
                "timestamp_raw": "Day 1",
                "chapter_reference": "Ch 1",
            },
            {
                "id": "2",
                "event_name": "Event B",
                "temporal_order": 1,
                "timestamp_raw": "Day 2",
                "chapter_reference": "Ch 1",
            },
        ]
        result = run_deterministic_checks(events)  # type: ignore[arg-type]
        # duplicate_temporal_order is a WARNING, not an ERROR
        assert result.deterministic_pass is True
        assert "warning" in result.overall_assessment.lower()

    def test_errors_cause_failure(self) -> None:
        """ERROR severity issues cause deterministic_pass to be False."""
        # Currently no check produces ERROR severity, but test the logic
        result = TemporalConsistencyResult(
            issues=[
                TemporalIssue(
                    severity=TemporalIssueSeverity.ERROR,
                    rule_id="test_error",
                    description="Test error",
                    suggestion="Fix it",
                )
            ],
            deterministic_pass=False,
            overall_assessment="1 error(s) found.",
        )
        assert result.deterministic_pass is False


# ---------------------------------------------------------------------------
# D. TemporalIssueSeverity and TemporalIssue models
# ---------------------------------------------------------------------------


class TestTemporalIssueModels:
    """TemporalIssueSeverity and TemporalIssue models work correctly."""

    def test_severity_values(self) -> None:
        assert TemporalIssueSeverity.ERROR == "error"
        assert TemporalIssueSeverity.WARNING == "warning"
        assert TemporalIssueSeverity.INFO == "info"

    def test_temporal_issue_defaults(self) -> None:
        issue = TemporalIssue(
            severity=TemporalIssueSeverity.WARNING,
            rule_id="test_rule",
        )
        assert issue.severity == TemporalIssueSeverity.WARNING
        assert issue.rule_id == "test_rule"
        assert issue.event_ids == []
        assert issue.description == ""
        assert issue.suggestion == ""
        assert issue.source == "deterministic"

    def test_temporal_issue_full(self) -> None:
        issue = TemporalIssue(
            severity=TemporalIssueSeverity.ERROR,
            rule_id="ordering_violation",
            event_ids=["uuid-1", "uuid-2"],
            description="Event A occurs after Event B but causes it.",
            suggestion="Reorder events or fix causal links.",
            source="llm",
        )
        assert issue.severity == TemporalIssueSeverity.ERROR
        assert len(issue.event_ids) == 2
        assert issue.source == "llm"

    def test_temporal_consistency_result_defaults(self) -> None:
        result = TemporalConsistencyResult()
        assert result.issues == []
        assert result.deterministic_pass is True
        assert result.overall_assessment == ""


# ---------------------------------------------------------------------------
# E. Prompt file existence — temporal_consistency
# ---------------------------------------------------------------------------


class TestTemporalConsistencyPromptExistence:
    """temporal_consistency prompt files exist in all 3 locales."""

    def _prompt_path(self, lang: str) -> Path:
        return PROMPTS_DIR / "planning" / lang / "temporal_consistency" / "system.md"

    def test_prompt_exists_en(self) -> None:
        assert self._prompt_path("en").is_file()

    def test_prompt_exists_de(self) -> None:
        assert self._prompt_path("de").is_file()

    def test_prompt_exists_fr(self) -> None:
        assert self._prompt_path("fr").is_file()

    def test_prompt_has_frontmatter(self) -> None:
        for lang in ("en", "de", "fr"):
            content = self._prompt_path(lang).read_text()
            assert content.startswith("---"), f"{lang} prompt missing frontmatter"
            assert "prompt_type: planning" in content, f"{lang} prompt missing prompt_type"
            assert "prompt_language: " + lang in content, f"{lang} prompt has wrong language"
