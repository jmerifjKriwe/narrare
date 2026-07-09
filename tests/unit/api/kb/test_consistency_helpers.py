"""Unit tests for consistency-analysis helpers.

Covers ``asymmetry_to_issue`` (both the with/without ``expected_inverse``
branches of the conditional ``suggested_resolution``) and
``generate_candidate_pairs`` (dedup by unordered pair, empty adjacency, and
the ``max_pairs`` cap).
"""

from __future__ import annotations

from narrare.kb._consistency_helpers import asymmetry_to_issue, generate_candidate_pairs
from narrare.kb.consistency_contracts import RelationshipAsymmetry
from narrare.kb.worldbuilding_contracts import ConsistencyCategory


def _asymmetry(*, expected_inverse: str | None) -> RelationshipAsymmetry:
    return RelationshipAsymmetry(
        source_id="s1",
        source_name="Anna",
        target_id="t1",
        target_name="Bob",
        forward_rel_type="parent_of",
        reverse_rel_type=None,
        expected_inverse=expected_inverse,
    )


class TestAsymmetryToIssue:
    def test_with_expected_inverse_adds_resolution(self) -> None:
        issue = asymmetry_to_issue(3, _asymmetry(expected_inverse="child_of"))

        assert issue.finding_index == 3
        assert issue.category == ConsistencyCategory.RELATIONSHIP_ASYMMETRY
        assert issue.entity_ids == ["s1", "t1"]
        assert issue.entity_names == ["Anna", "Bob"]
        assert issue.suggested_resolution is not None
        assert "child_of" in issue.suggested_resolution
        assert issue.confidence == 1.0

    def test_without_expected_inverse_has_no_resolution(self) -> None:
        issue = asymmetry_to_issue(0, _asymmetry(expected_inverse=None))

        assert issue.suggested_resolution is None
        assert "none" in issue.contradiction


class TestGenerateCandidatePairs:
    def test_empty_adjacency_returns_empty(self) -> None:
        assert generate_candidate_pairs({}) == []

    def test_dedupes_bidirectional_edges(self) -> None:
        """An a→b / b→a pair yields a single unordered candidate."""
        adjacency = {"a": {"b"}, "b": {"a"}}

        result = generate_candidate_pairs(adjacency)

        assert len(result) == 1
        assert set(result[0]) == {"a", "b"}

    def test_respects_max_pairs_cap(self) -> None:
        """The cap short-circuits once ``max_pairs`` candidates are found."""
        # Star graph: center connected to many leaves.
        leaves = [f"l{i}" for i in range(10)]
        adjacency = {"center": set(leaves)}
        for leaf in leaves:
            adjacency[leaf] = {"center"}

        result = generate_candidate_pairs(adjacency, max_pairs=4)

        assert len(result) == 4
