"""Tests for relationship formatting (FIND-009).

Covers:
1. format_relationships with valid edges
2. Empty / None input → empty string
3. Sorting is deterministic
4. Label falls back to rel_type when None
5. Multiple relationships grouped by source
"""

from __future__ import annotations

from narrare_core.writing._relationship_format import (
    RelationshipEdge,
    format_relationships,
)


class TestFormatRelationships:
    """format_relationships pure function tests."""

    def test_none_input_returns_empty_string(self) -> None:
        assert format_relationships(None) == ""

    def test_empty_list_returns_empty_string(self) -> None:
        assert format_relationships([]) == ""

    def test_single_edge(self) -> None:
        edges = [RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed")]
        result = format_relationships(edges)
        assert result == "Aria → [ally of] → Marcus"

    def test_label_used_over_rel_type(self) -> None:
        edges = [RelationshipEdge("Aria", "member_of", "member of", "Night Watch", "directed")]
        result = format_relationships(edges)
        assert result == "Aria → [member of] → Night Watch"

    def test_rel_type_used_when_label_is_none(self) -> None:
        edges = [RelationshipEdge("Aria", "ally_of", None, "Marcus", "directed")]
        result = format_relationships(edges)
        assert result == "Aria → [ally_of] → Marcus"

    def test_multiple_edges_sorted_by_source_name(self) -> None:
        edges = [
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
        ]
        result = format_relationships(edges)
        lines = result.split("\n")
        assert len(lines) == 2
        # Aria comes before Marcus alphabetically
        assert lines[0] == "Aria → [ally of] → Marcus"
        assert lines[1] == "Marcus → [rival of] → Elena"

    def test_multiple_edges_same_source_sorted_by_target(self) -> None:
        edges = [
            RelationshipEdge("Aria", "member_of", "member of", "Night Watch", "directed"),
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
        ]
        result = format_relationships(edges)
        lines = result.split("\n")
        assert len(lines) == 2
        # Both have same source, sorted by rel_type then target
        assert lines[0] == "Aria → [ally of] → Marcus"
        assert lines[1] == "Aria → [member of] → Night Watch"

    def test_mutual_direction_included(self) -> None:
        edges = [RelationshipEdge("Aria", "friend of", "friend of", "Elena", "mutual")]
        result = format_relationships(edges)
        assert result == "Aria → [friend of] → Elena"

    def test_accepts_plain_tuples(self) -> None:
        """The function accepts any Sequence of 5-tuples, not just RelationshipEdge."""
        edges = [
            ("Aria", "ally of", "ally of", "Marcus", "directed"),
        ]
        result = format_relationships(edges)
        assert result == "Aria → [ally of] → Marcus"

    def test_deterministic_output(self) -> None:
        """Same input always produces same output."""
        edges = [
            RelationshipEdge("Zara", "mentor of", "mentor of", "Aria", "directed"),
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
        ]
        result1 = format_relationships(edges)
        result2 = format_relationships(edges)
        assert result1 == result2

    def test_complex_scenario(self) -> None:
        """Realistic scenario with multiple characters and relationships."""
        edges = [
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
            RelationshipEdge("Aria", "member_of", "member of", "Night Watch", "directed"),
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
            RelationshipEdge("Elena", "mentor of", "mentor of", "Aria", "directed"),
        ]
        result = format_relationships(edges)
        lines = result.split("\n")
        assert len(lines) == 4
        assert lines[0] == "Aria → [ally of] → Marcus"
        assert lines[1] == "Aria → [member of] → Night Watch"
        assert lines[2] == "Elena → [mentor of] → Aria"
        assert lines[3] == "Marcus → [rival of] → Elena"
