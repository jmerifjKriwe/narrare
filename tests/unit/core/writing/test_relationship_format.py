"""Tests for relationship formatting (FIND-009).

Covers:
1. format_relationships with valid edges
2. Empty / None input → empty string
3. Sorting is deterministic
4. Label falls back to rel_type when None
5. Multiple relationships grouped by source
6. Count-based edge cap (Ruling 1): inert below cap, first-N + marker
   above cap, ``entry_count`` stays the pre-cap total
"""

from __future__ import annotations

from narrare_core.writing._relationship_format import (
    DEFAULT_MAX_RELATIONSHIP_EDGES,
    RelationshipEdge,
    format_relationships,
)


class TestFormatRelationships:
    """format_relationships pure function tests."""

    def test_none_input_returns_empty_string(self) -> None:
        assert format_relationships(None).text == ""

    def test_empty_list_returns_empty_string(self) -> None:
        assert format_relationships([]).text == ""

    def test_single_edge(self) -> None:
        edges = [RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed")]
        result = format_relationships(edges)
        assert result.text == "Aria → [ally of] → Marcus"

    def test_label_used_over_rel_type(self) -> None:
        edges = [RelationshipEdge("Aria", "member_of", "member of", "Night Watch", "directed")]
        result = format_relationships(edges)
        assert result.text == "Aria → [member of] → Night Watch"

    def test_rel_type_used_when_label_is_none(self) -> None:
        edges = [RelationshipEdge("Aria", "ally_of", None, "Marcus", "directed")]
        result = format_relationships(edges)
        assert result.text == "Aria → [ally_of] → Marcus"

    def test_multiple_edges_sorted_by_source_name(self) -> None:
        edges = [
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
        ]
        result = format_relationships(edges)
        lines = result.text.split("\n")
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
        lines = result.text.split("\n")
        assert len(lines) == 2
        # Both have same source, sorted by rel_type then target
        assert lines[0] == "Aria → [ally of] → Marcus"
        assert lines[1] == "Aria → [member of] → Night Watch"

    def test_mutual_direction_included(self) -> None:
        edges = [RelationshipEdge("Aria", "friend of", "friend of", "Elena", "mutual")]
        result = format_relationships(edges)
        assert result.text == "Aria → [friend of] → Elena"

    def test_accepts_plain_tuples(self) -> None:
        """The function accepts any Sequence of 5-tuples, not just RelationshipEdge."""
        edges = [
            ("Aria", "ally of", "ally of", "Marcus", "directed"),
        ]
        result = format_relationships(edges)
        assert result.text == "Aria → [ally of] → Marcus"

    def test_deterministic_output(self) -> None:
        """Same input always produces same output."""
        edges = [
            RelationshipEdge("Zara", "mentor of", "mentor of", "Aria", "directed"),
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
        ]
        result1 = format_relationships(edges)
        result2 = format_relationships(edges)
        assert result1.text == result2.text

    def test_complex_scenario(self) -> None:
        """Realistic scenario with multiple characters and relationships."""
        edges = [
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
            RelationshipEdge("Aria", "member_of", "member of", "Night Watch", "directed"),
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
            RelationshipEdge("Elena", "mentor of", "mentor of", "Aria", "directed"),
        ]
        result = format_relationships(edges)
        lines = result.text.split("\n")
        assert len(lines) == 4
        assert lines[0] == "Aria → [ally of] → Marcus"
        assert lines[1] == "Aria → [member of] → Night Watch"
        assert lines[2] == "Elena → [mentor of] → Aria"
        assert lines[3] == "Marcus → [rival of] → Elena"


class TestRelationshipEdgeCap:
    """Count-based edge cap at the core formatter (Ruling 1).

    Below the cap the output must be byte-identical to the uncapped render
    (inert path); above it, the deterministic first-N sorted lines are
    rendered plus an LLM-visible omission marker, while ``entry_count``
    keeps reporting the TOTAL pre-cap edge count (metadata = KB truth).
    """

    def test_default_cap_is_100(self) -> None:
        assert DEFAULT_MAX_RELATIONSHIP_EDGES == 100

    def test_below_cap_output_byte_identical_no_marker(self) -> None:
        """4 edges, explicit cap 100 → exact uncapped text, no marker line."""
        edges = [
            RelationshipEdge("Elena", "mentor of", "mentor of", "Aria", "directed"),
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
            RelationshipEdge("Aria", "member_of", "member of", "Night Watch", "directed"),
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
        ]
        result = format_relationships(edges, max_edges=100)
        assert result.text == (
            "Aria → [ally of] → Marcus\n"
            "Aria → [member of] → Night Watch\n"
            "Elena → [mentor of] → Aria\n"
            "Marcus → [rival of] → Elena"
        )
        assert "omitted" not in result.text
        assert result.entry_count == 4

    def test_default_param_inherits_module_default_below_cap(self) -> None:
        """Omitting max_edges uses DEFAULT_MAX_RELATIONSHIP_EDGES (inert here)."""
        edges = [
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
        ]
        result = format_relationships(edges)
        assert result.text == ("Aria → [ally of] → Marcus\nMarcus → [rival of] → Elena")

    def test_exceed_cap_renders_first_n_plus_marker(self) -> None:
        """5 edges, cap 3 → exactly the first 3 sorted lines + marker."""
        edges = [
            RelationshipEdge("Zara", "mentor of", "mentor of", "Aria", "directed"),
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
            RelationshipEdge("Aria", "member_of", "member of", "Night Watch", "directed"),
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
            RelationshipEdge("Elena", "mentor of", "mentor of", "Aria", "directed"),
        ]
        result = format_relationships(edges, max_edges=3)
        lines = result.text.split("\n")
        assert len(lines) == 4
        assert lines[0] == "Aria → [ally of] → Marcus"
        assert lines[1] == "Aria → [member of] → Night Watch"
        assert lines[2] == "Elena → [mentor of] → Aria"
        assert lines[3] == "[… 2 more relationships omitted]"
        # Line N+1 (Marcus, 4th in sort order) is absent from the render.
        assert "Marcus → [rival of] → Elena" not in result.text

    def test_at_cap_renders_all_no_marker(self) -> None:
        """Total == cap → all edges rendered, boundary produces NO marker."""
        edges = [
            RelationshipEdge("Aria", "ally of", "ally of", "Marcus", "directed"),
            RelationshipEdge("Aria", "member_of", "member of", "Night Watch", "directed"),
            RelationshipEdge("Marcus", "rival of", "rival of", "Elena", "directed"),
        ]
        result = format_relationships(edges, max_edges=3)
        assert result.text == (
            "Aria → [ally of] → Marcus\n"
            "Aria → [member of] → Night Watch\n"
            "Marcus → [rival of] → Elena"
        )
        assert "omitted" not in result.text
        assert result.entry_count == 3

    def test_default_cap_truncates_at_100_with_marker(self) -> None:
        """105 edges, default cap → 100 rendered lines + marker for 5 omitted."""
        edges = [
            RelationshipEdge(f"Src{i:03d}", "ally_of", None, f"Tgt{i:03d}", "directed")
            for i in range(105)
        ]
        result = format_relationships(edges)
        lines = result.text.split("\n")
        assert len(lines) == 101
        assert lines[0] == "Src000 → [ally_of] → Tgt000"
        assert lines[99] == "Src099 → [ally_of] → Tgt099"
        assert lines[100] == "[… 5 more relationships omitted]"
        # Line 101 (Src100) is absent.
        assert "Src100" not in result.text
        # Metadata keeps the pre-cap total.
        assert result.entry_count == 105

    def test_entry_count_total_while_rendered_capped(self) -> None:
        """entry_count == total pre-cap even though .text holds N edges."""
        edges = [RelationshipEdge(f"S{i}", "ally_of", None, f"T{i}", "directed") for i in range(7)]
        result = format_relationships(edges, max_edges=4)
        assert result.entry_count == 7
        rendered_lines = [ln for ln in result.text.split("\n") if "→" in ln]
        assert len(rendered_lines) == 4

    def test_shuffled_input_identical_output_under_cap(self) -> None:
        """Cap truncation happens after the sort → order-independent output."""
        edges = [
            RelationshipEdge(f"S{i:02d}", "rival_of", None, f"T{i:02d}", "directed")
            for i in range(6)
        ]
        forward = format_relationships(edges, max_edges=4)
        backward = format_relationships(list(reversed(edges)), max_edges=4)
        assert forward.text == backward.text

    def test_empty_and_none_with_explicit_cap_unchanged(self) -> None:
        """Empty / None input short-circuits before the cap — text stays ''."""
        assert format_relationships(None, max_edges=3).text == ""
        assert format_relationships([], max_edges=3).text == ""
        assert format_relationships(None, max_edges=3).entry_count == 0
        assert format_relationships([], max_edges=3).entry_count == 0
