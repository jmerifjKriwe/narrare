"""Unit tests for rule_helpers — deterministic KB pre-check and deduplication.

Pure function tests (no I/O, no mocking needed for the functions themselves).
"""

from __future__ import annotations

from narrare.consistency.rule_helpers import deduplicate_issues, rule_based_check
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyIssue,
    ConsistencySeverity,
)


def _issue(
    *,
    check_type: ConsistencyCheckType = ConsistencyCheckType.CHARACTER,
    severity: ConsistencySeverity = ConsistencySeverity.WARNING,
    description: str = "Something is inconsistent.",
    confidence: float = 0.8,
) -> ConsistencyIssue:
    """Create a test ConsistencyIssue with sensible defaults."""
    return ConsistencyIssue(
        check_type=check_type,
        severity=severity,
        description=description,
        locations=["Ch 1"],
        conflicting_facts=["fact A", "fact B"],
        confidence=confidence,
    )


# --- rule_based_check ---


class TestRuleBasedCheck:
    """Tests for the deterministic KB contradiction detector."""

    def test_empty_summaries_returns_empty(self) -> None:
        """No KB data → no issues."""
        assert rule_based_check([]) == []

    def test_single_entry_returns_empty(self) -> None:
        """Single entity can't conflict with itself."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Alice", "fields": {"age": "25"}},
        ]
        assert rule_based_check(summaries) == []

    def test_different_names_no_conflict(self) -> None:
        """Different entity names → no conflict, even with overlapping fields."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Alice", "fields": {"age": "25"}},
            {"entity_type": "character", "name": "Bob", "fields": {"age": "30"}},
        ]
        assert rule_based_check(summaries) == []

    def test_same_name_conflicting_field_produces_issue(self) -> None:
        """Same entity name with different values for the same field → issue."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Alice", "fields": {"eye_color": "blue"}},
            {"entity_type": "character", "name": "Alice", "fields": {"eye_color": "brown"}},
        ]
        issues = rule_based_check(summaries)
        assert len(issues) == 1
        issue = issues[0]
        assert issue.check_type == ConsistencyCheckType.CHARACTER
        assert issue.severity == ConsistencySeverity.WARNING
        assert issue.confidence == 1.0
        assert "Alice" in issue.description
        assert "eye_color" in issue.description
        assert "blue" in issue.description or "brown" in issue.description
        assert len(issue.conflicting_facts) == 2
        assert "Knowledge Base" in issue.locations

    def test_same_name_same_values_no_issue(self) -> None:
        """Same entity name with identical field values → no issue."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Alice", "fields": {"age": "25"}},
            {"entity_type": "character", "name": "Alice", "fields": {"age": "25"}},
        ]
        assert rule_based_check(summaries) == []

    def test_case_insensitive_name_matching(self) -> None:
        """Entity names are compared case-insensitively."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Alice", "fields": {"role": "hero"}},
            {"entity_type": "character", "name": "alice", "fields": {"role": "villain"}},
        ]
        issues = rule_based_check(summaries)
        assert len(issues) == 1
        assert "role" in issues[0].description

    def test_whitespace_trimmed_from_names(self) -> None:
        """Leading/trailing whitespace is stripped from entity names."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "  Alice  ", "fields": {"age": "25"}},
            {"entity_type": "character", "name": "alice", "fields": {"age": "30"}},
        ]
        issues = rule_based_check(summaries)
        assert len(issues) == 1

    def test_value_comparison_case_insensitive(self) -> None:
        """Field values are compared case-insensitively."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Tower", "fields": {"height": "100m"}},
            {"entity_type": "location", "name": "Tower", "fields": {"height": "100M"}},
        ]
        # Same value (case-insensitive) → no conflict
        assert rule_based_check(summaries) == []

    def test_multiple_conflicting_fields(self) -> None:
        """Multiple field mismatches produce separate issues."""
        summaries: list[dict[str, object]] = [
            {
                "entity_type": "character",
                "name": "Alice",
                "fields": {"age": "25", "hair": "blonde"},
            },
            {
                "entity_type": "character",
                "name": "Alice",
                "fields": {"age": "30", "hair": "brunette"},
            },
        ]
        issues = rule_based_check(summaries)
        assert len(issues) == 2
        descriptions = " ".join(i.description for i in issues)
        assert "age" in descriptions or "hair" in descriptions

    def test_entry_without_fields_skipped(self) -> None:
        """Entries with missing/None fields don't crash the check."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Alice"},
            {"entity_type": "character", "name": "Alice", "fields": {"age": "25"}},
        ]
        # Only one has fields → can't compare, no crash
        assert rule_based_check(summaries) == []

    def test_empty_name_skipped(self) -> None:
        """Entries with empty names are ignored."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "", "fields": {"age": "25"}},
            {"entity_type": "character", "name": "", "fields": {"age": "30"}},
        ]
        assert rule_based_check(summaries) == []

    def test_three_entries_with_conflict(self) -> None:
        """Three entries with same name and conflicting values → one issue."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Bob", "fields": {"role": "knight"}},
            {"entity_type": "character", "name": "Bob", "fields": {"role": "wizard"}},
            {"entity_type": "character", "name": "Bob", "fields": {"role": "king"}},
        ]
        issues = rule_based_check(summaries)
        assert len(issues) == 1
        assert len(issues[0].conflicting_facts) == 3

    def test_suggestion_includes_field_and_name(self) -> None:
        """Suggestion references the conflicting field and entity name."""
        summaries: list[dict[str, object]] = [
            {"entity_type": "character", "name": "Eve", "fields": {"rank": "general"}},
            {"entity_type": "character", "name": "Eve", "fields": {"rank": "private"}},
        ]
        issues = rule_based_check(summaries)
        assert len(issues) == 1
        assert issues[0].suggestion is not None
        assert "rank" in issues[0].suggestion
        assert "Eve" in issues[0].suggestion


# --- deduplicate_issues ---


class TestDeduplicateIssues:
    """Tests for the near-duplicate issue remover."""

    def test_empty_list_returns_empty(self) -> None:
        """No issues → no output."""
        assert deduplicate_issues([]) == []

    def test_unique_issues_preserved(self) -> None:
        """All unique issues are kept."""
        issues = [
            _issue(description="Issue A"),
            _issue(description="Issue B"),
            _issue(description="Issue C"),
        ]
        result = deduplicate_issues(issues)
        assert len(result) == 3

    def test_exact_duplicates_removed(self) -> None:
        """Issues with same type+severity+description → only first kept."""
        issues = [
            _issue(description="Eye color changes."),
            _issue(description="Eye color changes."),
        ]
        result = deduplicate_issues(issues)
        assert len(result) == 1

    def test_different_severity_kept(self) -> None:
        """Same description but different severity → both kept."""
        issues = [
            _issue(severity=ConsistencySeverity.WARNING, description="Timeline mismatch."),
            _issue(severity=ConsistencySeverity.ERROR, description="Timeline mismatch."),
        ]
        result = deduplicate_issues(issues)
        assert len(result) == 2

    def test_different_type_kept(self) -> None:
        """Same description but different check_type → both kept."""
        issues = [
            _issue(check_type=ConsistencyCheckType.CHARACTER, description="Conflicting data."),
            _issue(check_type=ConsistencyCheckType.TIMELINE, description="Conflicting data."),
        ]
        result = deduplicate_issues(issues)
        assert len(result) == 2

    def test_first_50_chars_used_for_comparison(self) -> None:
        """Only first 50 chars of description are compared."""
        short = "A" * 50
        long_a = short + "X" * 100
        long_b = short + "Y" * 100
        issues = [
            _issue(description=long_a),
            _issue(description=long_b),
        ]
        # First 50 chars are the same → deduplicated
        result = deduplicate_issues(issues)
        assert len(result) == 1

    def test_insertion_order_preserved(self) -> None:
        """First occurrence wins, order maintained."""
        issues = [
            _issue(description="Issue A", confidence=0.9),
            _issue(description="Issue A", confidence=0.5),
            _issue(description="Issue B", confidence=0.7),
        ]
        result = deduplicate_issues(issues)
        assert len(result) == 2
        assert result[0].confidence == 0.9  # First occurrence kept
        assert result[1].description == "Issue B"

    def test_rule_based_and_llm_overlap_deduped(self) -> None:
        """Simulates rule-based + LLM overlap scenario.

        When the first 50 chars of description match, the duplicate is removed.
        """
        rule_issue = _issue(
            description="Entity 'Alice' has conflicting 'eye_color' values: blue, brown",
            confidence=1.0,
        )
        llm_issue = _issue(
            description=(
                "Entity 'Alice' has conflicting 'eye_color' values: blue, brown (AI detected)"
            ),
            confidence=0.85,
        )
        # First 50 chars match → deduplicated (rule-based kept, confidence=1.0)
        result = deduplicate_issues([rule_issue, llm_issue])
        assert len(result) == 1
        assert result[0].confidence == 1.0

    def test_exact_same_50_chars_deduped(self) -> None:
        """If first 50 chars match exactly → deduped."""
        base = "Character 'Bob' has inconsistent age across chapters"
        rule_issue = _issue(description=base + " (rule)", confidence=1.0)
        llm_issue = _issue(description=base + " (LLM)", confidence=0.8)
        # First 50 chars of base = same → deduplicated
        result = deduplicate_issues([rule_issue, llm_issue])
        assert len(result) == 1
        assert result[0].confidence == 1.0  # First kept
